"""
File upload routes — Öğrencinin PDF/DOCX yüklemesi ve içerikten soru sorması.
"""
from __future__ import annotations

import uuid
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_ingestion_pipeline
from app.api.dependencies_auth import get_current_learner_id
from app.infrastructure.database import get_session
from app.services.content_rag.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    db: AsyncSession = Depends(get_session),
):
    """Öğrenci doküman yükler, chunklara bölünüp embed edilerek RAG'a eklenir."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dosya adı eksik.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya formatı: {ext}. Desteklenen: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya 10MB'dan büyük olamaz.")

    # Extract text based on file type
    text_content = ""
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                doc = fitz.open(tmp.name)
                text_content = "\n".join(page.get_text() for page in doc)
                doc.close()
        except ImportError:
            # Fallback: basit metin çıkarma
            text_content = content.decode("utf-8", errors="ignore")
    elif ext == ".docx":
        try:
            import docx
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                doc = docx.Document(tmp.name)
                text_content = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            text_content = content.decode("utf-8", errors="ignore")
    else:
        text_content = content.decode("utf-8", errors="ignore")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Dosyadan metin çıkarılamadı.")

    # Ingest: chunk + embed + store
    document_id = f"user_{learner_id}_{file.filename}"
    chunks_count = await pipeline.ingest(
        session=db,
        document_id=document_id,
        raw_text=text_content,
        metadata={"uploaded_by": str(learner_id), "filename": file.filename},
    )

    logger.info(
        "Document uploaded | learner=%s file=%s chunks=%d",
        learner_id, file.filename, chunks_count,
    )

    return {
        "message": f"Dosya başarıyla yüklendi ve {chunks_count} parçaya bölündü.",
        "document_id": document_id,
        "chunks_count": chunks_count,
    }
