"""Web chat portal — NVIDIA Nemotron response + ElevenLabs voice."""

from __future__ import annotations

import base64
import logging
import uuid

import asyncpg
import httpx
from fastapi import APIRouter, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import settings
from app.llm.chat import llm_chat
from app.llm.emergency import emergency_reply, is_emergency
from app.llm.groq_stt import transcribe

LAKSHMI_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

log = logging.getLogger(__name__)
router = APIRouter()

_SYSTEM = """You are Saath, a warm and caring AI health companion for aging Indian parents.

You are assisting Lakshmi Iyer, a 71-year-old woman in Bengaluru.

Her health profile:
- Conditions: Type 2 Diabetes, Hypertension, Hypothyroidism, CKD Stage 3a
- Medications (morning): Metformin 500mg, Amlodipine 5mg, Telmisartan 40mg, Levothyroxine 50mcg (empty stomach), Atorvastatin 10mg, Aspirin 75mg, Glipizide 5mg
- eGFR trend: 78 → 71 → 65 → 58 (declining — kidney health needs monitoring)
- Recent concern: 3 dizziness episodes after morning medications (Apr 4, 11, 18)

STRICT OUTPUT RULES — follow every one:
- Write ONLY plain conversational sentences. NO bullet points, NO lists, NO dashes.
- NO markdown: no bold (**), no italics (*), no headers (#), no code blocks.
- NO emojis whatsoever.
- Maximum 2-3 short sentences. This is read aloud — keep it brief.
- Never diagnose or prescribe. Say "please discuss with your doctor" for clinical decisions.
- If user reports chest pain, breathlessness, stroke symptoms, fainting, or severe injury — say exactly: "Please call emergency services at 112 immediately." and nothing else.
- Respond in the same language the user writes in (English or Hindi). Hindi responses must also follow all rules above — plain sentences, no lists."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    text: str
    audio_b64: str = ""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def chat_page() -> str:
    return _HTML


async def _recent_vitals_for_lakshmi() -> str:
    """Append smartwatch anomaly context to the chat system prompt."""
    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
    except Exception as exc:
        log.debug("chat_vitals_db_connect_failed err=%s", exc)
        return ""
    try:
        rows = await conn.fetch(
            """SELECT marker, severity, value, threshold, narrative, summary_date
               FROM vitals_anomaly
               WHERE senior_id = $1
               ORDER BY created_at DESC
               LIMIT 5""",
            LAKSHMI_SENIOR_ID,
        )
    except Exception as exc:
        log.debug("chat_vitals_query_failed err=%s", exc)
        return ""
    finally:
        await conn.close()

    if not rows:
        return ""
    lines = [
        f"- {r['summary_date']} · {r['severity']} · {r['narrative']}"
        for r in rows
    ]
    return (
        "\nRECENT SMARTWATCH FLAGS (from Galaxy Watch, last 5 most recent):\n"
        + "\n".join(lines)
        + "\nIf Lakshmi asks how she's been or mentions feeling off, "
        "reference these flags warmly without alarming her.\n"
    )


# Emergency guard moved to app.llm.emergency so the Telegram voice_agent
# and /chat share a single source of truth for emergency phrase matching.


@router.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    if is_emergency(req.message or ""):
        log.warning("chat_emergency_triggered text=%r", req.message[:120])
        return ChatResponse(text=emergency_reply("en"))

    system = _SYSTEM + await _recent_vitals_for_lakshmi()
    try:
        text = await llm_chat(system=system, user=req.message, max_tokens=120)
    except Exception as exc:
        log.error("chat_llm_failed err=%s", exc)
        text = "I'm having a little trouble right now. Please try again in a moment. 🙏"
    return ChatResponse(text=text)


@router.post("/tts")
async def tts(req: ChatRequest) -> ChatResponse:
    audio_b64 = await _tts(req.message)
    return ChatResponse(text="", audio_b64=audio_b64)


@router.post("/stt")
async def stt(audio: UploadFile) -> dict[str, str]:
    """Browser-agnostic speech-to-text. Record via MediaRecorder, POST here,
    we forward to Groq Whisper. Works in every browser (unlike Chrome's
    SpeechRecognition which depends on Google's servers being reachable).
    Requires GROQ_API_KEY in .env."""
    data = await audio.read()
    if not data:
        return {"text": "", "error": "empty audio"}
    text = await transcribe(data, filename=audio.filename or "voice.webm")
    if text is None:
        return {"text": "", "error": "groq_unavailable"}
    return {"text": text, "error": ""}


async def _tts(text: str) -> str:
    key = settings.elevenlabs_api_key
    if not key or key.startswith("change-me"):
        return ""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                headers={"xi-api-key": key},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode()
        log.warning("elevenlabs_error status=%d", resp.status_code)
    except Exception as exc:
        log.warning("elevenlabs_failed err=%s", exc)
    return ""


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saath — Voice Agent</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);
     min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{width:100%;max-width:480px;height:100vh;max-height:820px;
      background:#fff;border-radius:28px;overflow:hidden;
      display:flex;flex-direction:column;
      box-shadow:0 32px 100px rgba(0,0,0,.5)}
.header{background:linear-gradient(135deg,#1a73e8,#0d47a1);
        padding:22px 24px 16px;color:#fff}
.hrow{display:flex;align-items:center;gap:14px}
.av{width:48px;height:48px;border-radius:50%;background:rgba(255,255,255,.18);
    display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0}
.header h1{font-size:21px;font-weight:700;letter-spacing:-.3px}
.header p{font-size:12px;opacity:.75;margin-top:3px}
.pills{display:flex;gap:6px;margin-top:12px;flex-wrap:wrap}
.pill{background:rgba(255,255,255,.15);border-radius:20px;
      padding:3px 10px;font-size:11px;opacity:.9}
.msgs{flex:1;overflow-y:auto;padding:20px 18px;
      display:flex;flex-direction:column;gap:14px;background:#f8f9fa}
.msgs::-webkit-scrollbar{width:4px}
.msgs::-webkit-scrollbar-thumb{background:#dadce0;border-radius:4px}
.bub{max-width:82%;padding:13px 17px;border-radius:20px;
     font-size:15px;line-height:1.55;word-break:break-word}
.bub.user{background:#1a73e8;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}
.bub.bot{background:#fff;color:#202124;align-self:flex-start;
         border-bottom-left-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
.bub.bot.thinking{color:#9aa0a6;font-style:italic}
.replay-btn{display:inline-flex;align-items:center;gap:5px;margin-top:9px;
            background:#f1f3f4;border:none;border-radius:12px;
            padding:5px 12px;font-size:12px;cursor:pointer;color:#5f6368}
.replay-btn:hover{background:#e8eaed}
.replay-btn.needs-tap{background:#1a73e8;color:#fff;font-size:14px;
            padding:10px 18px;margin-top:12px;font-weight:600;
            animation:pulse 1.6s ease-in-out infinite;box-shadow:0 2px 8px rgba(26,115,232,.35)}
.replay-btn.needs-tap:hover{background:#1765cc}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
.bar{padding:14px 16px;border-top:1px solid #e8eaed;background:#fff;
     display:flex;gap:10px;align-items:center}
#inp{flex:1;padding:13px 18px;border:1.5px solid #dadce0;border-radius:26px;
     font-size:15px;outline:none;transition:border-color .2s;background:#f8f9fa}
#inp:focus{border-color:#1a73e8;background:#fff}
.icon-btn{width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;
          display:flex;align-items:center;justify-content:center;
          font-size:20px;transition:all .2s;flex-shrink:0}
#send-btn{background:#1a73e8;color:#fff}
#send-btn:hover{background:#1557b0}
#send-btn:disabled{background:#bbb;cursor:not-allowed}
#mic-btn{background:#f1f3f4;color:#5f6368}
#mic-btn:hover{background:#e8eaed}
#mic-btn.recording{background:#ea4335;color:#fff;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}
.hint{font-size:11px;color:#9aa0a6;text-align:center;padding:0 0 6px}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="hrow">
      <div class="av">🌿</div>
      <div>
        <h1>Saath</h1>
        <p>AI Voice Health Companion · Lakshmi Iyer</p>
      </div>
    </div>
    <div class="pills">
      <span class="pill">🧠 Ling 2.6 Flash</span>
      <span class="pill">🔊 ElevenLabs Voice</span>
      <span class="pill">🎙 Speak or Type</span>
    </div>
  </div>
  <div class="msgs" id="msgs">
    <div class="bub bot">
      Namaste Lakshmi! I'm Saath, your health companion.
      You can <strong>speak</strong> using the mic button or type below.
      Ask me about your medications, how you're feeling, or anything health-related. 🙏
    </div>
  </div>
  <div class="hint" id="hint"></div>
  <div class="bar">
    <button class="icon-btn" id="mic-btn" onclick="toggleMic()" title="Hold to speak">🎙</button>
    <input id="inp" type="text" placeholder="Or type your message…" autocomplete="off">
    <button class="icon-btn" id="send-btn" onclick="sendText()">▶</button>
  </div>
</div>

<script>
const inp     = document.getElementById('inp');
const msgs    = document.getElementById('msgs');
const sendBtn = document.getElementById('send-btn');
const micBtn  = document.getElementById('mic-btn');
const hint    = document.getElementById('hint');

let isRecording = false;

inp.addEventListener('keypress', e => { if (e.key === 'Enter') sendText(); });

// ── Voice input — browser-agnostic via MediaRecorder → /stt (Groq Whisper)
// Works in Chrome/Edge/Brave/Arc/Firefox. No dependency on Google's speech servers.

let mediaRec       = null;
let recordedChunks = [];
let activeStream   = null;

async function startMicRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    hint.textContent = 'Microphone not available in this browser.';
    return;
  }
  try {
    activeStream = await navigator.mediaDevices.getUserMedia({audio: true});
  } catch(e) {
    hint.textContent = 'Microphone permission denied. Allow mic access and try again.';
    return;
  }

  recordedChunks = [];
  const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '');
  try {
    mediaRec = mime ? new MediaRecorder(activeStream, {mimeType: mime}) : new MediaRecorder(activeStream);
  } catch(e) {
    hint.textContent = 'Could not start mic: ' + e.message;
    stopStream();
    return;
  }

  mediaRec.ondataavailable = e => { if (e.data && e.data.size > 0) recordedChunks.push(e.data); };

  mediaRec.onstop = async () => {
    stopStream();
    isRecording = false;
    micBtn.classList.remove('recording');
    micBtn.textContent = '🎙';
    if (!recordedChunks.length) { hint.textContent = ''; return; }

    hint.textContent = 'Transcribing…';
    const blob = new Blob(recordedChunks, {type: mediaRec.mimeType || 'audio/webm'});
    const ext  = (mediaRec.mimeType || '').includes('mp4') ? 'mp4' : 'webm';
    const form = new FormData();
    form.append('audio', blob, 'voice.' + ext);

    try {
      const r = await fetch('/stt', {method: 'POST', body: form});
      const d = await r.json();
      if (d.error === 'groq_unavailable') {
        hint.textContent = 'Voice transcription not configured on the server. Please type instead.';
        return;
      }
      if (!d.text) { hint.textContent = 'Sorry, I did not catch that. Please try again.'; return; }
      hint.textContent = '';
      inp.value = d.text;
      sendText();
    } catch(e) {
      hint.textContent = 'Could not reach the server. Please type instead.';
    }
  };

  mediaRec.start();
  isRecording = true;
  micBtn.classList.add('recording');
  micBtn.textContent = '⏹';
  hint.textContent = 'Listening… tap again to stop';
}

function stopStream() {
  if (activeStream) { activeStream.getTracks().forEach(t => t.stop()); activeStream = null; }
  mediaRec = null;
}

function toggleMic() {
  if (isRecording && mediaRec) { mediaRec.stop(); return; }
  startMicRecording();
}

// stopMic is inlined into mediaRec.onstop above — kept as a no-op shim for
// any legacy callers that may still exist elsewhere in the page.
function stopMic() {
  isRecording = false;
  micBtn.classList.remove('recording');
  micBtn.textContent = '🎙';
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function stripMarkdown(text) {
  return text
    .replace(/\\*\\*(.+?)\\*\\*/g, '$1')   // **bold**
    .replace(/\\*(.+?)\\*/g, '$1')        // *italic*
    .replace(/#{1,6}\\s*/g, '')          // ## headings
    .replace(/`{1,3}[^`]*`{1,3}/g, '') // `code`
    .replace(/^\\s*[-*•]\\s+/gm, '')      // bullet points
    .replace(/^\\s*\\d+\\.\\s+/gm, '')      // numbered lists
    .replace(/\\[([^\\]]+)\\]\\([^)]+\\)/g, '$1') // [links](url)
    .replace(/\\p{Extended_Pictographic}/gu, '')  // strip all emoji (keeps Hindi/Tamil)
    .replace(/\\n{2,}/g, ' ')           // collapse blank lines
    .replace(/\\n/g, ' ')               // single newlines → space
    .trim();
}

// ── Text / API ──────────────────────────────────────────────────────────────
let currentUtterance = null;

function speakNow(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-IN';
  u.rate = 0.92;
  currentUtterance = u;
  window.speechSynthesis.speak(u);
}

// Shared audio element — priming it inside a user gesture lets us set .src
// later (after the async fetch) and call .play() without the autoplay block.
const primedAudio = new Audio();
let audioPrimed = false;

function primeAudio() {
  if (audioPrimed) return;
  try {
    // 1ms of silent WAV — establishes user-gesture credit for subsequent plays.
    primedAudio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
    primedAudio.play().then(() => { audioPrimed = true; }).catch(() => {});
  } catch(_) {}
}

async function sendText() {
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  sendBtn.disabled = true;
  micBtn.disabled = true;

  primeAudio();  // runs inside the click/Enter gesture

  addBubble(text, 'user');
  const loading = addBubble('Thinking…', 'bot thinking');

  try {
    // Step 1 — get LLM text (~1-2s), speak immediately with browser TTS
    const r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const d = await r.json();

    const clean = stripMarkdown(d.text);
    loading.className = 'bub bot';
    loading.textContent = clean;

    // Fetch ElevenLabs audio. Always prefer Lakshmi's voice over browser TTS.
    // If the browser blocks autoplay after the async fetch, we surface a
    // large "Tap to hear" button the user can click — that click IS a valid
    // user gesture and always unlocks playback.
    const rb = document.createElement('button');
    rb.className = 'replay-btn';
    rb.innerHTML = '⏳ Loading voice…';
    rb.disabled = true;
    rb.style.opacity = '0.5';
    loading.appendChild(document.createElement('br'));
    loading.appendChild(rb);

    fetch('/tts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: clean})
    }).then(res => res.json()).then(t => {
      if (!t.audio_b64) {
        // ElevenLabs genuinely unavailable — only now fall back to browser TTS.
        rb.remove();
        speakNow(clean);
        return;
      }

      // Re-use the primed audio element so Chrome honors the original
      // user-gesture credit captured by primeAudio() on the send click.
      primedAudio.src = 'data:audio/mpeg;base64,' + t.audio_b64;
      try { primedAudio.load(); } catch(_) {}

      rb.disabled = false;
      rb.style.opacity = '1';
      rb.innerHTML = '▶ Replay';
      rb.onclick = () => { primedAudio.currentTime = 0; primedAudio.play().catch(() => {}); };

      // Auto-play — should succeed now that primedAudio was touched inside
      // the send click. If the browser still blocks, upgrade the button.
      primedAudio.play().catch(() => {
        rb.innerHTML = '🔊 Tap to hear Lakshmi';
        rb.classList.add('needs-tap');
      });
    }).catch(() => {
      rb.remove();
      speakNow(clean);
    });

  } catch(e) {
    loading.className = 'bub bot';
    loading.textContent = 'Something went wrong. Please try again.';
  }

  sendBtn.disabled = false;
  micBtn.disabled = false;
  inp.focus();
}

function addBubble(text, cls) {
  const el = document.createElement('div');
  el.className = 'bub ' + cls;
  el.textContent = text;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}
</script>
</body>
</html>"""
