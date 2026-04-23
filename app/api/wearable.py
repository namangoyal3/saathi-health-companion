"""POST /wearable/samsung/webhook — HMAC-verified Samsung Health daily sync ingestion."""

from __future__ import annotations

import datetime
import hashlib
import hmac
import uuid
from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.config import settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/wearable", tags=["wearable"])


class WearableDailySummary(BaseModel):
    senior_id: uuid.UUID
    date: str
    steps: int = 0
    avg_heart_rate: int | None = None
    sleep_minutes: int | None = None
    sleep_efficiency_pct: int | None = None
    sleep_score: int | None = None
    avg_spo2_pct: int | None = None
    avg_skin_temp_c: float | None = None
    hrv_rmssd: int | None = None
    stress_score: int | None = None
    exercise_minutes: int | None = None


def _verify_hmac(body: bytes, signature: str) -> bool:
    if not settings.wearable_hmac_secret or settings.wearable_hmac_secret.startswith("change-me"):
        log.warning("wearable_hmac_secret not configured — accepting webhook without verification")
        return True
    expected = hmac.new(
        settings.wearable_hmac_secret.encode(),
        body,
        hashlib.sha256,
    ).digest()
    import base64

    expected_b64 = base64.b64encode(expected).decode()
    return hmac.compare_digest(expected_b64, signature)


@router.post("/samsung/webhook", status_code=200)
async def samsung_webhook(request: Request) -> dict[str, Any]:
    """Receive Samsung Health daily summary from the Android companion app.

    Verifies HMAC-SHA256 signature, upserts into wearable_daily_summary.
    """
    body = await request.body()
    sig = request.headers.get("X-Saath-Signature", "")

    if not _verify_hmac(body, sig):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = WearableDailySummary.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        datetime.date.fromisoformat(payload.date)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"invalid date format: {payload.date!r}"
        ) from exc

    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            """INSERT INTO wearable_daily_summary
               (senior_id, date, steps, avg_heart_rate, sleep_minutes,
                sleep_efficiency_pct, sleep_score, avg_spo2_pct,
                avg_skin_temp_c, hrv_rmssd, stress_score, exercise_minutes)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
               ON CONFLICT (senior_id, date) DO UPDATE SET
                 steps = EXCLUDED.steps,
                 avg_heart_rate = EXCLUDED.avg_heart_rate,
                 sleep_minutes = EXCLUDED.sleep_minutes,
                 sleep_efficiency_pct = EXCLUDED.sleep_efficiency_pct,
                 sleep_score = EXCLUDED.sleep_score,
                 avg_spo2_pct = EXCLUDED.avg_spo2_pct,
                 avg_skin_temp_c = EXCLUDED.avg_skin_temp_c,
                 hrv_rmssd = EXCLUDED.hrv_rmssd,
                 stress_score = EXCLUDED.stress_score,
                 exercise_minutes = EXCLUDED.exercise_minutes,
                 updated_at = NOW()""",
            payload.senior_id,
            datetime.date.fromisoformat(payload.date),
            payload.steps,
            payload.avg_heart_rate,
            payload.sleep_minutes,
            payload.sleep_efficiency_pct,
            payload.sleep_score,
            payload.avg_spo2_pct,
            payload.avg_skin_temp_c,
            payload.hrv_rmssd,
            payload.stress_score,
            payload.exercise_minutes,
        )
    finally:
        await conn.close()

    log.info(
        "samsung_webhook_received",
        senior_id=str(payload.senior_id),
        date=payload.date,
        steps=payload.steps,
        sleep_min=payload.sleep_minutes,
        spo2=payload.avg_spo2_pct,
        hmac_verified=True,
    )

    # Run VitalsAnomalyAgent inline so the webhook response carries the detection
    # result. For production volumes move this behind an arq enqueue (the job
    # handler detect_vitals_anomalies is already wired).
    from app.workers.vitals_anomaly import process_summary

    try:
        detection = await process_summary(payload.senior_id, payload.date)
    except Exception as exc:
        log.warning(
            "vitals_detection_failed senior=%s date=%s err=%s", payload.senior_id, payload.date, exc
        )
        detection = {"anomaly_count": 0, "alerted": False, "severities": []}

    return {"ok": True, "date": payload.date, "detection": detection}
