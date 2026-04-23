# Saath

AI health companion for aging Indian parents and their NRI children. See:

- [`docs/Saath_PRD_v3_1_Final.md`](docs/Saath_PRD_v3_1_Final.md) — product requirements.
- [`docs/Saath_TechSpec_v1_0.extracted.txt`](docs/Saath_TechSpec_v1_0.extracted.txt) — engineering spec (plain-text extraction of the original .docx).
- [`docs/docs-verification-2026-04-23.md`](docs/docs-verification-2026-04-23.md) — verified deltas between the Tech Spec and current Anthropic docs; trust this file over the spec where they disagree.
- [`CLAUDE.md`](CLAUDE.md) — Claude Code working context.

## Quickstart

```bash
docker compose up -d db redis
uv sync
cp .env.example .env                # fill in ANTHROPIC_API_KEY etc.
uv run alembic upgrade head
uv run python scripts/seed_personas.py
uv run pytest tests/test_day1_smoke.py -v
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
curl -sf http://localhost:8080/health | jq .
```

## Build timeline

Hackathon submission: 2026-04-26 20:00 EST. Day-by-day sequencing in PRD §11 and Tech Spec §13.

## Status

Day 1 foundation. Senior voice pipeline + IVR + lab vision + Doctor Report pipeline arrive in Days 2–5.
