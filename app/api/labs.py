"""POST /lab-pdf — multipart lab PDF upload, R2 storage, arq enqueue, 202 response."""

from __future__ import annotations

import hashlib
import logging
import uuid

import asyncpg
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import get_db  # noqa: F401 — kept for future auth middleware

log = logging.getLogger(__name__)

router = APIRouter(prefix="/lab-pdf", tags=["labs"])

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_MIME = {"application/pdf", "application/x-pdf"}


def _r2_client() -> object:
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


@router.post("", status_code=202)
async def upload_lab_pdf(
    file: UploadFile,
    senior_id: uuid.UUID,
) -> JSONResponse:
    """Accept a lab PDF, upload to R2, insert lab_panel row, enqueue parsing job.

    Returns 202 with panel_id + job_id immediately.
    """
    # MIME guard
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_MIME and not file.filename.endswith(".pdf"):  # type: ignore[union-attr]
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    panel_id = uuid.uuid4()
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    r2_key = f"labs/{senior_id}/{panel_id}_{file_hash}.pdf"

    # Upload to R2 (skip if not configured — dev mode)
    if settings.r2_account_id and settings.r2_access_key_id:
        import asyncio

        s3 = _r2_client()
        await asyncio.to_thread(
            s3.put_object,  # type: ignore[attr-defined]
            Bucket=settings.r2_bucket,
            Key=r2_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        source_key: str | None = r2_key
        local: str | None = None
    else:
        # Dev mode: write to tmp and pass local path
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
        source_key = None
        local = tmp.name
        log.info("lab_pdf_dev_mode panel_id=%s path=%s", panel_id, local)

    # Persist lab_panel row
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            """INSERT INTO lab_panel (id, senior_id, status, r2_key, filename)
               VALUES ($1, $2, 'parsing', $3, $4)""",
            panel_id,
            senior_id,
            source_key,
            file.filename,
        )
    finally:
        await conn.close()

    # Enqueue arq job
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    job = await redis.enqueue_job(
        "process_lab_pdf",
        str(panel_id),
        r2_key=source_key,
        local_path=local,
    )
    await redis.close()

    return JSONResponse(
        status_code=202,
        content={
            "panel_id": str(panel_id),
            "job_id": job.job_id if job else None,
            "status": "parsing",
        },
    )
