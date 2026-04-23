"""Priya (guardian) web chat portal.

Mirror of the Lakshmi chat at `/` but scoped to Priya, the NRI daughter guardian.
System prompt is guardian-oriented: Saathi summarizes Lakshmi's recent health
state from:
  - wearable_daily_summary (latest row)
  - vitals_anomaly (last 5)
  - bot_med_event (adherence today, if the Telegram bot logs exist)
  - agent_flag (last 7d, filtered to HIGH/URGENT)

Every turn is persisted to bot_conv_memory under a stable synthetic chat_id
(PRIYA_DEMO_CHAT_ID) so the admin dashboard Conversation Viewer lights up.
"""

from __future__ import annotations

import logging
import uuid

import asyncpg
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import settings
from app.llm.chat import llm_chat

log = logging.getLogger(__name__)
router = APIRouter()

LAKSHMI_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PRIYA_GUARDIAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

# Stable synthetic chat_id for Priya's web demo turns. High enough not to
# collide with real Telegram ids (which are usually < 2^32 for bots).
PRIYA_DEMO_CHAT_ID = 770000002


_SYSTEM = """You are Saath, a warm AI health companion speaking to Priya Iyer in San Jose.
Priya is the adult daughter of Lakshmi Iyer (71F, Bengaluru, senior) — her guardian.
Priya is paying for the service. She wants concise, guardian-level updates.

Lakshmi's baseline:
- Conditions: Type 2 Diabetes, Hypertension, Hypothyroidism, CKD Stage 3a
- Medications (AM): Metformin 500mg, Amlodipine 5mg, Telmisartan 40mg,
  Levothyroxine 50mcg, Atorvastatin 10mg, Aspirin 75mg, Glipizide 5mg
- eGFR trend: 78 → 71 → 65 → 58 (declining)
- Recent concern: 3 post-AM-medication dizziness episodes (Apr 4/11/18)

STRICT OUTPUT RULES — follow every one:
- Plain conversational sentences. NO markdown, NO bullet points, NO emojis.
- Maximum 3 short sentences. Read aloud — keep it tight.
- Guardian tone: factual, not alarming; suggest physician review for HIGH/URGENT.
- NEVER diagnose. Use "may benefit from physician review" language for clinical nuance.
- If emergency terms appear (chest pain, stroke symptoms, severe bleeding, etc.):
  reply exactly "Please call emergency services at 112 in India or 911 in the US immediately." and nothing else.
- Respond in the same language Priya writes in (English or Hindi)."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    text: str


async def _lakshmi_context() -> str:
    """Build a compact 'what's going on with Lakshmi' briefing for Priya."""
    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
    except Exception:
        return ""

    try:
        latest_summary = await conn.fetchrow(
            """SELECT date, steps, avg_heart_rate, avg_spo2_pct, sleep_minutes,
                      hrv_rmssd, stress_score
               FROM wearable_daily_summary
               WHERE senior_id = $1
               ORDER BY date DESC LIMIT 1""",
            LAKSHMI_SENIOR_ID,
        )
        anomalies = await conn.fetch(
            """SELECT marker, severity, value, narrative, summary_date
               FROM vitals_anomaly
               WHERE senior_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            LAKSHMI_SENIOR_ID,
        )
        flags = await conn.fetch(
            """SELECT severity, flag_type, finding, created_at
               FROM agent_flag
               WHERE senior_id = $1
                 AND created_at > NOW() - INTERVAL '7 days'
                 AND severity IN ('HIGH','URGENT')
               ORDER BY created_at DESC LIMIT 5""",
            LAKSHMI_SENIOR_ID,
        )
    finally:
        await conn.close()

    parts: list[str] = []
    if latest_summary:
        parts.append(
            "LATEST GALAXY WATCH DAY ("
            f"{latest_summary['date'].isoformat()}): "
            f"HR={latest_summary['avg_heart_rate']} "
            f"SpO2={latest_summary['avg_spo2_pct']}% "
            f"Steps={latest_summary['steps']} "
            f"Sleep={latest_summary['sleep_minutes']}m "
            f"HRV={latest_summary['hrv_rmssd']} "
            f"Stress={latest_summary['stress_score']}"
        )
    if anomalies:
        parts.append(
            "RECENT SMARTWATCH ANOMALIES:\n"
            + "\n".join(
                f"- {a['summary_date']} · {a['severity']} · {a['narrative']}" for a in anomalies
            )
        )
    if flags:
        parts.append(
            "RECENT CLINICAL FLAGS (HIGH/URGENT, 7d):\n"
            + "\n".join(f"- {f['severity']} · {f['flag_type']} · {f['finding']}" for f in flags)
        )
    return "\n\n".join(parts)


async def _persist_turn(role: str, content: str) -> None:
    """Append one conversation turn to bot_conv_memory so the admin viewer sees it."""
    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
    except Exception:
        return
    try:
        # Make sure a bot_profile exists for PRIYA_DEMO_CHAT_ID so the admin
        # dashboard lists her in the Profiles card. Upsert is idempotent.
        await conn.execute(
            """INSERT INTO bot_profile (chat_id, name, language, conditions)
               VALUES ($1, 'Priya Iyer (web demo)', 'en', '[]'::jsonb)
               ON CONFLICT (chat_id) DO NOTHING""",
            PRIYA_DEMO_CHAT_ID,
        )
        await conn.execute(
            """INSERT INTO bot_conv_memory (chat_id, role, content)
               VALUES ($1, $2, $3)""",
            PRIYA_DEMO_CHAT_ID,
            role,
            content,
        )
    except Exception as exc:
        log.warning("priya_persist_failed err=%s", exc)
    finally:
        await conn.close()


async def _history() -> list[dict[str, str]]:
    """Return the last 10 turns so the LLM has conversational memory."""
    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
    except Exception:
        return []
    try:
        rows = await conn.fetch(
            """SELECT role, content FROM bot_conv_memory
               WHERE chat_id = $1 ORDER BY created_at DESC LIMIT 10""",
            PRIYA_DEMO_CHAT_ID,
        )
    finally:
        await conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


@router.get("/priya", response_class=HTMLResponse, include_in_schema=False)
async def priya_page() -> str:
    return _HTML


@router.post("/priya/chat")
async def priya_chat(req: ChatRequest) -> ChatResponse:
    context = await _lakshmi_context()
    system = _SYSTEM + ("\n\n" + context if context else "")
    history = await _history()

    await _persist_turn("user", req.message)
    try:
        text = await llm_chat(
            system=system,
            user=req.message,
            history=history,
            max_tokens=160,
        )
    except Exception as exc:
        log.error("priya_llm_failed err=%s", exc)
        text = "I'm having trouble reaching the model right now. Please try again shortly."
    await _persist_turn("assistant", text)
    return ChatResponse(text=text)


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saath — Priya (Guardian)</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: linear-gradient(135deg, #1e3a8a, #312e81, #4c1d95);
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
}
.card {
  width: 100%; max-width: 500px; height: 100vh; max-height: 860px;
  background: #fff; border-radius: 28px; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: 0 32px 100px rgba(0,0,0,.5);
}
.header {
  background: linear-gradient(135deg, #6366f1, #312e81);
  padding: 22px 24px 18px; color: #fff;
}
.hrow { display: flex; align-items: center; gap: 14px; }
.av {
  width: 52px; height: 52px; border-radius: 50%;
  background: rgba(255,255,255,.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; flex-shrink: 0;
}
.header h1 { font-size: 20px; font-weight: 700; letter-spacing: -.3px; }
.header .sub { font-size: 12px; opacity: .78; margin-top: 3px; }
.pills { display: flex; gap: 6px; margin-top: 14px; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,.16); border-radius: 20px;
  padding: 4px 11px; font-size: 11px; opacity: .92;
}
.msgs {
  flex: 1; overflow-y: auto; padding: 22px 18px;
  display: flex; flex-direction: column; gap: 14px; background: #f8fafc;
}
.msgs::-webkit-scrollbar { width: 4px; }
.msgs::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
.bub {
  max-width: 82%; padding: 13px 17px; border-radius: 20px;
  font-size: 15px; line-height: 1.5; word-break: break-word;
}
.bub.user {
  background: #6366f1; color: #fff; align-self: flex-end;
  border-bottom-right-radius: 4px;
}
.bub.bot {
  background: #fff; color: #0f172a; align-self: flex-start;
  border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.bub.bot.thinking { color: #94a3b8; font-style: italic; }
.bar {
  padding: 14px 16px; border-top: 1px solid #e2e8f0; background: #fff;
  display: flex; gap: 10px; align-items: center;
}
#inp {
  flex: 1; padding: 13px 18px; border: 1.5px solid #cbd5e1; border-radius: 26px;
  font-size: 15px; outline: none; transition: border-color .2s; background: #f8fafc;
}
#inp:focus { border-color: #6366f1; background: #fff; }
#send-btn {
  width: 48px; height: 48px; border-radius: 50%; border: none; cursor: pointer;
  background: #6366f1; color: #fff; font-size: 20px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: background .2s;
}
#send-btn:hover { background: #4f46e5; }
#send-btn:disabled { background: #cbd5e1; cursor: not-allowed; }
.suggestions {
  display: flex; gap: 6px; flex-wrap: wrap; padding: 0 18px 12px; background: #f8fafc;
}
.sugg {
  background: #eef2ff; color: #4338ca; border: 1px solid #c7d2fe;
  border-radius: 16px; padding: 6px 12px; font-size: 12px; cursor: pointer;
}
.sugg:hover { background: #e0e7ff; }
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="hrow">
        <div class="av">👩🏽</div>
        <div>
          <h1>Saath — Priya's Dashboard</h1>
          <div class="sub">Guardian view · Lakshmi Iyer (71F, Bengaluru)</div>
        </div>
      </div>
      <div class="pills">
        <span class="pill">Guardian · NRI (San Jose)</span>
        <span class="pill">Senior: Lakshmi</span>
        <span class="pill">Vitals synced via Galaxy Watch</span>
      </div>
    </div>
    <div class="msgs" id="msgs">
      <div class="bub bot">Hi Priya — I'm Saathi. Ask me anything about how Lakshmi is doing today.</div>
    </div>
    <div class="suggestions">
      <span class="sugg" onclick="ask(this.textContent)">How is Mom doing today?</span>
      <span class="sugg" onclick="ask(this.textContent)">Any red flags from her watch?</span>
      <span class="sugg" onclick="ask(this.textContent)">Did she take her morning meds?</span>
      <span class="sugg" onclick="ask(this.textContent)">Summarize the week</span>
    </div>
    <div class="bar">
      <input id="inp" placeholder="Type your message..." autocomplete="off" autofocus>
      <button id="send-btn" onclick="send()">➤</button>
    </div>
  </div>

<script>
const msgs = document.getElementById('msgs');
const inp = document.getElementById('inp');
const btn = document.getElementById('send-btn');

inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });

function add(role, text, extraClass = '') {
  const el = document.createElement('div');
  el.className = `bub ${role} ${extraClass}`.trim();
  el.textContent = text;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}

function ask(q) { inp.value = q; send(); }

async function send() {
  const text = inp.value.trim();
  if (!text) return;
  inp.value = ''; btn.disabled = true;
  add('user', text);
  const thinking = add('bot', 'thinking…', 'thinking');

  try {
    const res = await fetch('/priya/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text}),
    });
    const data = await res.json();
    thinking.remove();
    add('bot', data.text || '(no response)');
  } catch (e) {
    thinking.remove();
    add('bot', 'Network error — please try again.');
  } finally {
    btn.disabled = false; inp.focus();
  }
}
</script>
</body>
</html>"""
