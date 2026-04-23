"""Web chat portal — NVIDIA Nemotron response + ElevenLabs voice."""

from __future__ import annotations

import base64
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import settings
from app.llm.nvidia import nvidia_chat

log = logging.getLogger(__name__)
router = APIRouter()

_SYSTEM = """You are Saath, a warm and caring AI health companion for aging Indian parents.

You are assisting Lakshmi Iyer, a 71-year-old woman in Bengaluru.

Her health profile:
- Conditions: Type 2 Diabetes, Hypertension, Hypothyroidism, CKD Stage 3a
- Medications (morning): Metformin 500mg, Amlodipine 5mg, Telmisartan 40mg, Levothyroxine 50mcg (empty stomach), Atorvastatin 10mg, Aspirin 75mg, Glipizide 5mg
- eGFR trend: 78 → 71 → 65 → 58 (declining — kidney health needs monitoring)
- Recent concern: 3 dizziness episodes after morning medications (Apr 4, 11, 18)

Rules:
- Speak warmly and simply, like a trusted companion — not a doctor
- Keep answers short: 2-3 sentences for voice playback
- Never diagnose or prescribe. Say "please discuss with your doctor" for clinical decisions
- If user reports chest pain, breathlessness, stroke symptoms, fainting, or severe injury — say exactly: "Please call emergency services at 112 immediately." and nothing else
- Respond in the same language the user writes in (English or Hindi)"""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    text: str
    audio_b64: str = ""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def chat_page() -> str:
    return _HTML


@router.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        text = await nvidia_chat(system=_SYSTEM, user=req.message, max_tokens=200)
    except Exception as exc:
        log.error("chat_llm_failed err=%s", exc)
        text = "I'm having a little trouble right now. Please try again in a moment. 🙏"
    audio_b64 = await _tts(text)
    return ChatResponse(text=text, audio_b64=audio_b64)


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
      <span class="pill">🧠 NVIDIA Llama 3.1</span>
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

let recognition = null;
let isRecording = false;

inp.addEventListener('keypress', e => { if (e.key === 'Enter') sendText(); });

// ── Voice input setup ───────────────────────────────────────────────────────
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRec) {
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-IN';

  recognition.onstart = () => {
    isRecording = true;
    micBtn.classList.add('recording');
    micBtn.textContent = '⏹';
    hint.textContent = '🎙 Listening… speak now';
  };

  recognition.onresult = e => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
    inp.value = transcript;
    if (e.results[e.results.length-1].isFinal) {
      hint.textContent = '';
      stopMic();
      sendText();
    }
  };

  recognition.onerror = err => {
    hint.textContent = 'Mic error: ' + err.error + '. Try typing instead.';
    stopMic();
  };

  recognition.onend = () => stopMic();
} else {
  micBtn.title = 'Speech not supported in this browser (use Chrome/Edge)';
  micBtn.style.opacity = '.4';
  micBtn.onclick = () => { hint.textContent = 'Use Chrome or Edge for voice input.'; };
}

function toggleMic() {
  if (!recognition) return;
  if (isRecording) { recognition.stop(); return; }
  inp.value = '';
  recognition.start();
}

function stopMic() {
  isRecording = false;
  micBtn.classList.remove('recording');
  micBtn.textContent = '🎙';
}

// ── Text / API ──────────────────────────────────────────────────────────────
async function sendText() {
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  sendBtn.disabled = true;
  micBtn.disabled = true;

  addBubble(text, 'user');
  const loading = addBubble('Thinking…', 'bot thinking');

  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const d = await r.json();

    loading.className = 'bub bot';
    loading.textContent = d.text;

    if (d.audio_b64) {
      const audio = new Audio('data:audio/mpeg;base64,' + d.audio_b64);
      audio.play().catch(() => {});
      const rb = document.createElement('button');
      rb.className = 'replay-btn';
      rb.innerHTML = '▶ Replay';
      rb.onclick = () => new Audio('data:audio/mpeg;base64,' + d.audio_b64).play();
      loading.appendChild(document.createElement('br'));
      loading.appendChild(rb);
    } else {
      hint.textContent = 'ⓘ Voice disabled — add ELEVENLABS_API_KEY to .env';
    }
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
