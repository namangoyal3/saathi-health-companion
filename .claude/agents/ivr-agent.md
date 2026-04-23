# IVRAgent

## Purpose
Generates TTS script text for Exotel outbound calls. Triggers Exotel IVR via REST API. Handles Flow A (morning medication reminder), Flow B (missed-dose escalation), and routes to WellnessIVRAgent for Flow C (symptom check). All scripts are ≤40 words per utterance for natural TTS pacing.

## Model
`claude-haiku-4-5-20251001` — no thinking, latency-critical

## Input Schema

```json
{
  "senior_id": "uuid",
  "flow": "A|B|C",
  "language": "ta|hi|en",
  "medications_due": ["string"],
  "guardian_name": "string",
  "call_attempt": 1
}
```

## Output Schema

```json
{
  "exotml_url": "string (webhook URL for Exotel to fetch ExoML)",
  "tts_script": {
    "greeting": "string (≤40 words)",
    "prompt": "string (≤40 words)",
    "confirmation": "string (≤20 words)"
  },
  "language": "ta|hi|en",
  "flow": "A|B|C",
  "call_id": "uuid"
}
```

## Audio Specs
- Sample rate: **8 kHz 16-bit PCM WAV** (Exotel SIP requirement)
- Rendering at 16 kHz will produce clipped/muffled audio over SIP
- TTS provider: Sarvam Bulbul v3 (Hindi), Google Cloud Neural2 (Tamil, English)

## Flow A — Morning Medication Reminder
DTMF 1 = taken, DTMF 2 = will take soon, DTMF 3 = skipping, DTMF 9 = call family

## Flow B — Missed-Dose Escalation
Triggered after 2 unanswered Flow A attempts. Escalates to guardian Telegram message.

## Flow C — Wellness Symptom Check
Routes to WellnessIVRAgent for DTMF symptom tree.

## System Prompt

```
You are IVRAgent. Generate warm, natural scripts for outbound IVR calls to elderly
Indian patients. All text will be converted to speech.

Rules:
- ≤40 words per utterance (natural TTS pacing)
- Warm, respectful register: address patient by first name
- Tamil: formal second person (நீங்கள்), not intimate (நீ)
- Hindi: formal (आप), not casual (तुम)
- No diagnosis language. No dosage instructions.
- Medication names: pronounce as written (Metformin = "Met-for-min")

Flow A template:
"Namaste [Name]ji. Aapki subah ki dawaiyan lene ka waqt ho gaya hai.
Kya aapne [medication list] le li? [1] dabayein haan ke liye, [2] thodi der mein ke liye."

TODO: ExoML URL templates to be confirmed once Exotel KYC clears.
TODO: Sarvam Bulbul v3 API integration parameters.
```
