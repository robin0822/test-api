from datetime import datetime, timezone
from pathlib import Path
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import DocumentRecord
from app.parser import ParseError, extract_document
from app.summarizer import summarize_document


def _now():
    return datetime.now(timezone.utc)


@celery_app.task(bind=True)
def process_document(self, record_id: str):
    db = SessionLocal()
    record = db.get(DocumentRecord, record_id)
    if not record:
        db.close()
        return
    path = Path(record.temp_path) if record.temp_path else None
    try:
        record.status, record.progress, record.started_at = "PARSING", 10, _now()
        db.commit()
        if record.extracted_text:
            text = record.extracted_text
        elif path:
            text = extract_document(str(path))
            record.extracted_text, record.temp_path = text, None
            record.status, record.progress = "SUMMARIZING", 50
            db.commit()
        else:
            raise ParseError("No source file or extracted text available")
        if path:
            path.unlink(missing_ok=True)
        record.summary = summarize_document(text, record.file_name)
        record.status, record.progress = "SUCCESS", 100
        record.error_code = record.error_message = record.extracted_text = None
        record.completed_at = _now()
        db.commit()
    except ParseError as exc:
        record.status, record.progress, record.error_code = "FAILED", 100, "DOCUMENT_PARSE_FAILED"
        record.error_message, record.completed_at = str(exc)[:2000], _now()
        db.commit()
    except Exception as exc:
        record.status, record.progress, record.error_code = "FAILED", 100, "MODEL_SUMMARY_FAILED"
        record.error_message, record.completed_at = str(exc)[:2000], _now()
        db.commit()
    finally:
        if path:
            path.unlink(missing_ok=True)
        db.close()
