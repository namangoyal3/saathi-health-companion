# Saath — Claude Code working context

**Status as of 2026-04-23:** greenfield. Day 1 foundation (this commit) wires the
Postgres + Redis + subagent scaffolding. Voice pipeline, IVR, lab vision, and the
Doctor Visit Report pipeline arrive on Days 2–5.

## What this repo is

An AI health companion for aging Indian parents (the "senior") and their NRI /
metro adult children (the "guardian"). Read in this order:

1. [`docs/Saath_PRD_v3_1_Final.md`](docs/Saath_PRD_v3_1_Final.md) — product requirements.
2. [`docs/Saath_TechSpec_v1_0.extracted.txt`](docs/Saath_TechSpec_v1_0.extracted.txt) — engineering spec, plain text extract of the .docx.
3. [`docs/docs-verification-2026-04-23.md`](docs/docs-verification-2026-04-23.md) — **trust this over the Tech Spec** where they disagree. Notably: Opus 4.7 uses adaptive thinking only, `type:"enabled"` is rejected.

The repo layout mirrors Tech Spec §15.1 (`app/`, `evals/personas/`,
`.claude/agents/`, `scripts/`, `migrations/versions/`).

## How to run

```bash
docker compose up -d db redis
uv sync
cp .env.example .env                 # fill ANTHROPIC_API_KEY
uv run alembic upgrade head
uv run python scripts/seed_personas.py    # idempotent
uv run pytest tests/test_day1_smoke.py -v
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## LLM model rules — non-negotiable

| When | Model | Thinking | Why |
|------|-------|----------|-----|
| Voice turn (IVR, Telegram chat) | **Haiku 4.5** (`claude-haiku-4-5-20251001`) | off | ~200 ms TTFT; <1 s p50. **Never** block on Opus. |
| Intent classification, response shortening, safety gatekeeper | **Haiku 4.5** | off | Latency-critical per egress. |
| Lab PDF vision parse | **Opus 4.7** (`claude-opus-4-7`) | adaptive, effort=`medium` | 2,576 px vision; structured JSON. |
| Daily brief narrative | **Opus 4.7** | adaptive, effort=`medium` | Quality bar is one paragraph. |
| Longitudinal lab synthesis | **Opus 4.7** | adaptive, effort=`high` | Multi-quarter trend reasoning over 1M context. |
| Doctor Visit Report synthesis | **Opus 4.7** | adaptive, effort=`high` | Clinician-grade prose; 3-sentence exec summary. |
| **DDISubAgent only** | **Opus 4.7** | adaptive, effort=`xhigh`, `display:"summarized"` | Pharmacology reasoning; extended-thinking trace is the demo moment. |

Opus 4.7 adaptive thinking shape (from [docs-verification](docs/docs-verification-2026-04-23.md) — **not** what the Tech Spec §5.2 shows):

```python
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    thinking={"type": "adaptive", "display": "summarized"},
    output_config={"effort": "xhigh"},    # low | medium | high (default) | xhigh | max
    tools=[{"type": "memory_20250818", "name": "memory"}, ...],
    messages=[...],
    metadata={"agent": "DDISubAgent", "senior_id": str(senior_id)},
)
```

`type:"enabled"` with `budget_tokens` is **rejected** on Opus 4.7 with HTTP 400.
`display` defaults to `"omitted"` on Opus 4.7 so **set `"summarized"` explicitly**
whenever we need the trace. No `anthropic-beta` header is required for this call.

Every Anthropic call **must** include `metadata={"agent": "<name>", "senior_id": <uuid|None>}`
so Langfuse traces are filterable.

## Safety contract — also non-negotiable

Every user- or physician-facing string routes through the `safety-gatekeeper` subagent
([`.claude/agents/safety-gatekeeper.md`](.claude/agents/safety-gatekeeper.md)). **Never**
bypass, even on "internal" endpoints — if a string eventually reaches the dashboard,
a PDF, an IVR call, or Telegram, it goes through the gatekeeper.

| Forbidden | Allowed |
|-----------|---------|
| `"you have diabetes"` | `"eGFR has declined from 58 to 55"` |
| `"abnormal"`, `"your screening result"` | `"consider discussing with a physician"` |
| `"take 5 mg of X"`, `"reduce to 2.5 mg"` | `"informational summary, physician review recommended"` |
| specific-disease probability numbers | `"associated with Amlodipine + Telmisartan in the literature"` |

Emergency terms (chest pain, severe breathlessness, stroke symptoms, suicidal ideation,
fainting, acute severe injury) trigger the emergency protocol — the gatekeeper does
**not** rewrite them, it sets `emergency=true` on its output and the caller pages
Priya with a priority flag and voices the India emergency number 112.

## Subagents (.claude/agents/)

Thirteen declarative contracts. Each has `purpose | model | effort | input schema |
output schema | system prompt`. **When asked to build or debug a specific agent,
read that agent file first.** Tech Spec §4 is the source of truth.

Fully spec'd for Day 1: `ddi-subagent.md`, `safety-gatekeeper.md`. The other 11
are stubs with TODO markers for pieces the spec doesn't nail down — don't invent.

## Personas (locked)

Three synthetic personas live under [`evals/personas/`](evals/personas/) with
deterministic UUIDs so every test, seed, and demo references the same rows.

| Persona | Role | Locale | Purpose |
|---------|------|--------|---------|
| **Lakshmi Iyer** (71F, Bengaluru, Tamil/Hindi) | senior | `ta` primary | Canonical demo. T2DM + HTN + Hypothyroidism + CKD-3a. 7 medications. 4-quarter eGFR decline 78→71→65→58. Three post-AM-dose dizziness episodes Apr 4 / 11 / 18. |
| **Priya Iyer** (34F, San Jose) | guardian | `en` | Paying user. Consented to all categories. Receives daily brief + URGENT alerts. |
| **Meera Sharma** (68F, Delhi, Hindi-primary) | senior | `hi` primary | Test persona. T2D + HTN only, no CKD. Validates the flows generalize beyond Lakshmi. |
| **Rajesh** (55M, cardiovascular) | senior | `en`/`hi` | Exercises the Cardiology report variant. |

Meera is explicitly a **test-only** persona — do not treat her data as a second
canonical demo. Per PRD §3.2 the demo stars Lakshmi and Priya.

## Data sources of truth

- **Filesystem `/memories/{user_id}/`** — source of truth for the senior's profile,
  active regimen, and consent matrix. Read/write through the memory tool adapter
  ([`app/llm/memory.py`](app/llm/memory.py)). The adapter path-canonicalizes every
  request into `MEMORY_ROOT/{user_id}/` — never let a model access anything else.
- **Postgres** — source of truth for events: medication reminders, lab panels,
  biomarkers, IVR call logs, Telegram inbound, agent flags, daily summaries,
  doctor reports. Schema lives in [`migrations/versions/001_init.py`](migrations/versions/001_init.py).

## Known gotchas

- **Anthropic beta headers:** the Tech Spec has a placeholder `extended-thinking-2025-xx-xx`
  — **does not exist**. Remove it everywhere. The memory tool does **not** require
  any beta header. `context-management-2025-06-27` is only needed when we turn on
  context-editing strategies (we don't for Day 1).
- **Opus 4.7 `display`:** defaults to `"omitted"` on Opus 4.7 — silent change from
  4.6. Always set `"summarized"` when we want the DDI trace visible.
- **Exotel TTS audio:** needs 8 kHz 16-bit PCM WAV. Rendering at 16 kHz will
  produce clipped / muffled audio over SIP.
- **WeasyPrint (Day 4):** the Docker image must install Noto Sans Devanagari +
  Noto Sans Tamil system fonts or Hindi/Tamil glyphs render as tofu.
- **Memory tool path isolation:** `/memories/{user_id}/` per senior. **Never**
  share across users. The adapter must reject any `view`/`create`/etc. whose
  resolved path isn't inside the authorized senior's root.
- **pgcrypto + uuid-ossp extensions:** must be created before the first migration
  runs. `001_init.py` does this before `CREATE TABLE`.
- **Auto-idempotent seed:** `scripts/seed_personas.py` uses `ON CONFLICT DO NOTHING`
  throughout — running it twice is a no-op by design.

## Constraints

- Python 3.12, `uv` for deps, async-first (FastAPI, SQLAlchemy 2.0 async, asyncpg,
  `httpx.AsyncClient`).
- **Never `print()` in `app/`** — use `structlog`. `scripts/` and `evals/` are allowed to print.
- Strict mypy on `app/` (`uv run mypy app`). Type hints everywhere in application code.
- `uv run pre-commit run --all-files` must pass before a step is considered complete.
- No secrets in code. All credentials go through `.env` + `pydantic-settings`.

## When Claude Code is working on Saath

1. Read the relevant agent contract in `.claude/agents/` first.
2. If touching the Opus path, consult [`docs/docs-verification-2026-04-23.md`](docs/docs-verification-2026-04-23.md) before pinning any API shape.
3. If adding a user-facing string, route it through `safety-gatekeeper` — always.
4. If unsure which model to use, re-read the "LLM model rules" table above.
