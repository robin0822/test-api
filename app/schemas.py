from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ErrorInfo(BaseModel):
    code: str
    message: str


class DocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    file_name: str
    file_type: str
    file_size: int
    status: str
    progress: int
    summary: dict[str, Any] | None = None
    error: ErrorInfo | None = None
    retry_count: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_url: str


class UploadResponse(BaseModel):
    batch_id: str
    total: int
    records: list[DocumentItem]


class BatchResponse(BaseModel):
    batch_id: str
    status: str
    total: int
    pending_count: int
    processing_count: int
    success_count: int
    failed_count: int
    records: list[DocumentItem]


class HistoryResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[DocumentItem]
