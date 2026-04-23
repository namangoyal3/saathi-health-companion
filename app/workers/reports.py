"""arq worker: Doctor Visit Report generation jobs (Day 4: ReportSupervisor)."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings


async def generate_doctor_report(
    ctx: dict[str, object],
    senior_id: str,
    guardian_id: str,
    report_type: str,
) -> dict[str, object]:
    """Generate Doctor Visit Report PDF. TODO Day 4."""
    return {
        "senior_id": senior_id,
        "guardian_id": guardian_id,
        "report_type": report_type,
        "status": "pending_day4_implementation",
    }


class WorkerSettings:
    functions: ClassVar[list[object]] = [generate_doctor_report]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 600  # 10 min; report generation includes Opus calls + PDF render
    max_jobs = 3
