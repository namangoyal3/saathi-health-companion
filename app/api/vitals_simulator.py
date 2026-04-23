"""Vitals simulator — demo UI + scenario POST endpoints.

Wraps the existing /wearable/samsung/webhook so demo operators don't need a real
Galaxy Watch. Posts scripted daily-summary payloads that trigger the anomaly detector.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import uuid
from typing import Any

import asyncpg
import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import settings

log = structlog.get_logger(__name__)
router = APIRouter(tags=["vitals-simulator"])
_templates = Jinja2Templates(directory="app/templates")


SCENARIOS: dict[str, dict[str, Any]] = {
    "normal": {
        "label": "Normal day",
        "steps": 6500,
        "avg_heart_rate": 72,
        "sleep_minutes": 420,
        "sleep_efficiency_pct": 88,
        "sleep_score": 85,
        "avg_spo2_pct": 98,
        "avg_skin_temp_c": 36.6,
        "hrv_rmssd": 42,
        "stress_score": 35,
        "exercise_minutes": 45,
    },
    "post_med_hr_spike": {
        "label": "Post-med HR spike",
        "steps": 4200,
        "avg_heart_rate": 108,
        "sleep_minutes": 390,
        "sleep_efficiency_pct": 80,
        "sleep_score": 72,
        "avg_spo2_pct": 96,
        "avg_skin_temp_c": 36.7,
        "hrv_rmssd": 28,
        "stress_score": 62,
        "exercise_minutes": 30,
    },
    "spo2_dip": {
        "label": "SpO₂ dip",
        "steps": 3100,
        "avg_heart_rate": 78,
        "sleep_minutes": 360,
        "sleep_efficiency_pct": 75,
        "sleep_score": 68,
        "avg_spo2_pct": 88,
        "avg_skin_temp_c": 36.8,
        "hrv_rmssd": 32,
        "stress_score": 58,
        "exercise_minutes": 18,
    },
    "low_step_fatigue": {
        "label": "Low-step fatigue",
        "steps": 1800,
        "avg_heart_rate": 74,
        "sleep_minutes": 300,
        "sleep_efficiency_pct": 70,
        "sleep_score": 58,
        "avg_spo2_pct": 97,
        "avg_skin_temp_c": 36.9,
        "hrv_rmssd": 30,
        "stress_score": 55,
        "exercise_minutes": 8,
    },
    "dizziness_episode": {
        "label": "Dizziness episode ⚡ (Lakshmi Apr 4/11/18)",
        "steps": 1600,
        "avg_heart_rate": 112,
        "sleep_minutes": 270,
        "sleep_efficiency_pct": 64,
        "sleep_score": 48,
        "avg_spo2_pct": 88,
        "avg_skin_temp_c": 37.1,
        "hrv_rmssd": 18,
        "stress_score": 78,
        "exercise_minutes": 5,
    },
}


class SimulatorRequest(BaseModel):
    senior_id: uuid.UUID
    scenario: str
    date: str | None = None  # ISO YYYY-MM-DD; defaults to today


def _pg_dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _sign(body: bytes) -> str:
    secret = settings.wearable_hmac_secret.encode()
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


@router.get("/vitals-simulator", response_class=HTMLResponse)
async def simulator_page(request: Request) -> Any:
    """Serve the Galaxy Watch simulator UI."""
    return _templates.TemplateResponse(
        request,
        "vitals_simulator.html",
        {"scenarios": SCENARIOS},
    )


@router.post("/api/vitals-simulator/send")
async def simulator_send(req: SimulatorRequest, request: Request) -> dict[str, Any]:
    """Build a scenario payload, sign it, POST to /wearable/samsung/webhook."""
    if req.scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"unknown scenario {req.scenario!r}")

    scenario = SCENARIOS[req.scenario]
    date_str = req.date or datetime.date.today().isoformat()

    # Mirror WearableDailySummary schema (app/api/wearable.py)
    body = {
        "senior_id": str(req.senior_id),
        "date": date_str,
        "steps": scenario["steps"],
        "avg_heart_rate": scenario["avg_heart_rate"],
        "sleep_minutes": scenario["sleep_minutes"],
        "sleep_efficiency_pct": scenario["sleep_efficiency_pct"],
        "sleep_score": scenario["sleep_score"],
        "avg_spo2_pct": scenario["avg_spo2_pct"],
        "avg_skin_temp_c": scenario["avg_skin_temp_c"],
        "hrv_rmssd": scenario["hrv_rmssd"],
        "stress_score": scenario["stress_score"],
        "exercise_minutes": scenario["exercise_minutes"],
    }
    body_bytes = json.dumps(body).encode()
    signature = _sign(body_bytes)

    # Hit our own app — use the incoming host so localhost + remote both work
    base = str(request.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base}/wearable/samsung/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Saath-Signature": signature,
            },
        )

    try:
        upstream = resp.json()
    except Exception:
        upstream = {"status_code": resp.status_code, "text": resp.text[:500]}

    log.info(
        "simulator_send",
        scenario=req.scenario,
        senior_id=str(req.senior_id),
        date=date_str,
        upstream_status=resp.status_code,
    )
    return {
        "ok": resp.status_code == 200,
        "scenario": req.scenario,
        "date": date_str,
        "posted_payload": body,
        "upstream": upstream,
    }


@router.get("/api/vitals-simulator/status/{senior_id}")
async def simulator_status(senior_id: uuid.UUID) -> dict[str, Any]:
    """Latest daily summary + last 5 anomalies for the status panel."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn=_pg_dsn())
    try:
        summary_row = await conn.fetchrow(
            """SELECT date, steps, avg_heart_rate, sleep_minutes,
                      avg_spo2_pct, avg_skin_temp_c, hrv_rmssd, stress_score
               FROM wearable_daily_summary
               WHERE senior_id = $1
               ORDER BY date DESC LIMIT 1""",
            senior_id,
        )
        anomaly_rows = await conn.fetch(
            """SELECT marker, severity, value, threshold, narrative,
                      summary_date, alerted_at, created_at
               FROM vitals_anomaly
               WHERE senior_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            senior_id,
        )

        last_summary = (
            {
                "date": summary_row["date"].isoformat(),
                "steps": summary_row["steps"],
                "avg_heart_rate": summary_row["avg_heart_rate"],
                "sleep_minutes": summary_row["sleep_minutes"],
                "avg_spo2_pct": summary_row["avg_spo2_pct"],
                "avg_skin_temp_c": float(summary_row["avg_skin_temp_c"])
                if summary_row["avg_skin_temp_c"] is not None
                else None,
                "hrv_rmssd": summary_row["hrv_rmssd"],
                "stress_score": summary_row["stress_score"],
            }
            if summary_row
            else None
        )
        anomalies = [
            {
                "marker": row["marker"],
                "severity": row["severity"],
                "value": float(row["value"]),
                "threshold": float(row["threshold"]),
                "narrative": row["narrative"],
                "summary_date": row["summary_date"].isoformat(),
                "alerted": row["alerted_at"] is not None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in anomaly_rows
        ]
        return {"last_summary": last_summary, "recent_anomalies": anomalies}
    finally:
        await conn.close()
