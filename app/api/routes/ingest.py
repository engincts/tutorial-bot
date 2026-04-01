"""POST /ingest — döküman yükleme"""
from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_ingestion_pipeline
from app.infrastructure.database import get_session
from app.services.content_rag.ingestion_pipeline import IngestionPipeline

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestOut(BaseModel):
    document_id: str
    chunks_written: int
    chars_total: int


@router.post("/text", response_model=IngestOut)
async def ingest_text(
    document_id: str = Form(...),
    text: str = Form(...),
    kc_tags: str = Form(default=""),  # virgülle ayrılmış
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    db: AsyncSession = Depends(get_session),
) -> IngestOut:
    tags = [t.strip() for t in kc_tags.split(",") if t.strip()]
    result = await pipeline.ingest_text(
        session=db,
        document_id=document_id,
        text=text,
        kc_tags=tags,
    )
    return IngestOut(
        document_id=result.document_id,
        chunks_written=result.chunks_written,
        chars_total=result.chars_total,
    )


@router.post("/pdf", response_model=IngestOut)
async def ingest_pdf(
    document_id: str = Form(...),
    kc_tags: str = Form(default=""),
    file: UploadFile = File(...),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    db: AsyncSession = Depends(get_session),
) -> IngestOut:
    tags = [t.strip() for t in kc_tags.split(",") if t.strip()]
    pdf_bytes = await file.read()
    result = await pipeline.ingest_pdf(
        session=db,
        document_id=document_id,
        pdf_bytes=pdf_bytes,
        kc_tags=tags,
    )
    return IngestOut(
        document_id=result.document_id,
        chunks_written=result.chunks_written,
        chars_total=result.chars_total,
    )
