import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import DocumentRecord
from app.schemas import BatchResponse, DocumentItem, ErrorInfo, HistoryResponse, UploadResponse
from app.tasks import process_document

settings = get_settings()
ALLOWED_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


def require_token(authorization: str | None = Header(default=None)):
    if settings.api_token and authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid API token")


def item(record: DocumentRecord) -> DocumentItem:
    error = ErrorInfo(code=record.error_code, message=record.error_message or "") if record.error_code else None
    values = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    values.update(error=error, result_url=f"/api/v1/documents/{record.id}")
    return DocumentItem.model_validate(values)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    return """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>Document Summary API</title>
    <style>body{font:18px system-ui;max-width:760px;margin:80px auto;padding:24px;background:#07111f;color:#eef5ff}a{color:#72d8ff}</style>
    <h1>Document Summary API</h1><p>Word / Excel 异步总结服务运行正常。</p>
    <p><a href='/docs'>打开 Swagger 接口文档</a> · <a href='/health'>健康检查</a></p></html>"""


@app.get("/health")
def health():
    return {"status": "ok", "service": "document-summary-api"}


@app.post("/api/v1/documents", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_token)])
async def upload_documents(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    if not files or len(files) > settings.max_batch_files:
        raise HTTPException(400, f"A batch must contain 1-{settings.max_batch_files} files")
    batch_id = str(uuid.uuid4())
    records: list[DocumentRecord] = []
    created_paths: list[Path] = []
    try:
        for uploaded in files:
            file_name = Path(uploaded.filename or "unnamed").name
            extension = Path(file_name).suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(415, f"Unsupported file type: {extension}")
            record_id = str(uuid.uuid4())
            target = Path(settings.upload_dir) / f"{record_id}{extension}"
            size = 0
            with target.open("wb") as output:
                while chunk := await uploaded.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_file_size:
                        raise HTTPException(413, f"File exceeds 20 MB: {file_name}")
                    output.write(chunk)
            created_paths.append(target)
            record = DocumentRecord(id=record_id, batch_id=batch_id, file_name=file_name, file_type=extension, file_size=size, temp_path=str(target))
            db.add(record)
            records.append(record)
            await uploaded.close()
        db.commit()
    except Exception:
        db.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    for record in records:
        task = process_document.delay(record.id)
        record.celery_task_id = task.id
    db.commit()
    return UploadResponse(batch_id=batch_id, total=len(records), records=[item(record) for record in records])


@app.get("/api/v1/documents/{record_id}", response_model=DocumentItem, dependencies=[Depends(require_token)])
def get_document(record_id: str, db: Session = Depends(get_db)):
    record = db.get(DocumentRecord, record_id)
    if not record:
        raise HTTPException(404, "Document record not found")
    return item(record)


@app.get("/api/v1/batches/{batch_id}", response_model=BatchResponse, dependencies=[Depends(require_token)])
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    records = list(db.scalars(select(DocumentRecord).where(DocumentRecord.batch_id == batch_id).order_by(DocumentRecord.created_at)))
    if not records:
        raise HTTPException(404, "Batch not found")
    counts = {name: sum(record.status == name for record in records) for name in ("PENDING", "PARSING", "SUMMARIZING", "SUCCESS", "FAILED")}
    processing = counts["PARSING"] + counts["SUMMARIZING"]
    batch_status = "SUCCESS" if counts["SUCCESS"] == len(records) else "FAILED" if counts["FAILED"] == len(records) else "PROCESSING"
    return BatchResponse(batch_id=batch_id, status=batch_status, total=len(records), pending_count=counts["PENDING"], processing_count=processing, success_count=counts["SUCCESS"], failed_count=counts["FAILED"], records=[item(record) for record in records])


@app.get("/api/v1/documents", response_model=HistoryResponse, dependencies=[Depends(require_token)])
def history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), record_status: str | None = Query(None, alias="status"), file_type: str | None = None, db: Session = Depends(get_db)):
    filters = []
    if record_status:
        filters.append(DocumentRecord.status == record_status.upper())
    if file_type:
        normalized = file_type if file_type.startswith(".") else f".{file_type}"
        filters.append(DocumentRecord.file_type == normalized.lower())
    total = db.scalar(select(func.count()).select_from(DocumentRecord).where(*filters)) or 0
    query = select(DocumentRecord).where(*filters).order_by(DocumentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    records = list(db.scalars(query))
    return HistoryResponse(page=page, page_size=page_size, total=total, items=[item(record) for record in records])


@app.post("/api/v1/documents/{record_id}/retry", response_model=DocumentItem, status_code=202, dependencies=[Depends(require_token)])
def retry_document(record_id: str, db: Session = Depends(get_db)):
    record = db.get(DocumentRecord, record_id)
    if not record:
        raise HTTPException(404, "Document record not found")
    if record.status != "FAILED":
        raise HTTPException(409, "Only failed records can be retried")
    if not record.extracted_text:
        raise HTTPException(409, "Original file was deleted; re-upload is required")
    record.status, record.progress = "PENDING", 0
    record.error_code = record.error_message = None
    record.retry_count += 1
    task = process_document.delay(record.id)
    record.celery_task_id = task.id
    db.commit()
    return item(record)
