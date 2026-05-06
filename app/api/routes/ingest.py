"""POST /ingest — döküman yükleme"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_ingestion_pipeline
from app.api.dependencies_auth import get_current_learner_id
from app.infrastructure.database import get_session
from app.services.content_rag.ingestion_pipeline import IngestionPipeline

router = APIRouter(prefix="/ingest", tags=["ingest"])

_MAX_TEXT_CHARS = 500_000          # ~500 KB metin
_MAX_PDF_BYTES = 100 * 1024 * 1024  # 100 MB
_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


class IngestOut(BaseModel):
    document_id: str
    chunks_written: int
    chars_total: int


@router.post("/text", response_model=IngestOut)
async def ingest_text(
    document_id: str = Form(...),
    text: str = Form(...),
    kc_tags: str = Form(default=""),  # virgülle ayrılmış
    _: uuid.UUID = Depends(get_current_learner_id),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    db: AsyncSession = Depends(get_session),
) -> IngestOut:
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text boş olamaz")
    if len(text) > _MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"text çok büyük — maks {_MAX_TEXT_CHARS:,} karakter",
        )

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
    _: uuid.UUID = Depends(get_current_learner_id),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    db: AsyncSession = Depends(get_session),
) -> IngestOut:
    if file.content_type not in _PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz dosya türü: {file.content_type!r} — yalnızca PDF kabul edilir",
        )

    pdf_bytes = await file.read()

    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dosya boş")
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF çok büyük — maks {_MAX_PDF_BYTES // 1_048_576} MB, gelen: {len(pdf_bytes) / 1_048_576:.1f} MB",
        )

    tags = [t.strip() for t in kc_tags.split(",") if t.strip()]
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
