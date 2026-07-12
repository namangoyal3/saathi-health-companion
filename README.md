# Saath

Multimodal AI health-companion prototype for aging Indian parents and the family members who support them.

## Current build

- Specialist agents for medication adherence, drug interactions, lab results, symptoms, vitals anomalies, and safety.
- Voice and IVR flows backed by Exotel/FreeSWITCH and speech services.
- Lab-report vision ingestion and a structured doctor-report workflow.
- Authenticated wearable ingestion from the Android companion app.
- Unit, integration, lab-vision, and safety red-team evaluations.

## Architecture

The FastAPI service coordinates domain-specific agents and deterministic safety checks around PostgreSQL and Redis. Voice, document-vision, and wearable channels feed the same longitudinal patient context while keeping urgent and uncertain cases explicit.

## Quickstart

```bash
docker compose up -d db redis
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_personas.py
uv run pytest
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
curl -sf http://localhost:8080/health | jq .
```

Set the required provider variables documented in `.env.example` before starting the API.

## Product and engineering docs

- [Product requirements](docs/Saath_PRD_v3_1_Final.md)
- [Engineering specification](docs/Saath_TechSpec_v1_0.extracted.txt)
- [Documentation verification notes](docs/docs-verification-2026-04-23.md)
- [Android companion](android/saath-companion/README.md)

Saath is a prototype for decision support. It does not diagnose conditions, replace a clinician, or provide emergency services.
