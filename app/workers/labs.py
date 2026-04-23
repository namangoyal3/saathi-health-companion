"""arq worker: lab PDF processing jobs (Day 3: Opus 4.7 vision pipeline)."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings


async def process_lab_pdf(ctx: dict[str, object], panel_id: str) -> dict[str, object]:
    """Parse a lab panel PDF using Opus 4.7 vision. TODO Day 3."""
    return {"panel_id": panel_id, "status": "pending_day3_implementation"}


class WorkerSettings:
    functions: ClassVar[list[object]] = [process_lab_pdf]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 300
    max_jobs = 10
