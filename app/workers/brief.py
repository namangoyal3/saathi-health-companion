"""arq worker: daily brief generation jobs (Day 4: BriefSupervisor fan-out)."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings


async def generate_daily_brief(
    ctx: dict[str, object], senior_id: str, date: str
) -> dict[str, object]:
    """Generate daily health brief for a senior. TODO Day 4."""
    return {"senior_id": senior_id, "date": date, "status": "pending_day4_implementation"}


async def check_missed_medications(ctx: dict[str, object]) -> dict[str, object]:
    """Escalation check: any overdue medication events. TODO Day 3."""
    return {"status": "pending_day3_implementation"}


class WorkerSettings:
    functions: ClassVar[list[object]] = [generate_daily_brief, check_missed_medications]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 120
    max_jobs = 5
