"""ExoML Jinja2 templates for IVR flows A/B/C in each supported language.

Each script renders ExoML XML. The /ivr/exoml/{script_id} endpoint serves these
when Exotel fetches the call URL. TTS audio URLs are injected at render time.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined

_env = Environment(autoescape=True, undefined=StrictUndefined)

# --------------------------------------------------------------------------- #
# Base ExoML snippets
# --------------------------------------------------------------------------- #

_FLOW_A_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ prompt_url }}</Play>
  <Gather numDigits="1" timeout="8"
          action="{{ webhook_base }}/ivr/webhook/exotel?call_id={{ call_id }}&amp;step=dtmf">
    <Play>{{ repeat_url }}</Play>
  </Gather>
  <Play>{{ no_input_url }}</Play>
  <Hangup/>
</Response>""")

_FLOW_A_DTMF1_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ confirm_url }}</Play>
  <Hangup/>
</Response>""")

_FLOW_A_DTMF2_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ skip_ack_url }}</Play>
  <Hangup/>
</Response>""")

_FLOW_B_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ urgent_prompt_url }}</Play>
  <Gather numDigits="1" timeout="10"
          action="{{ webhook_base }}/ivr/webhook/exotel?call_id={{ call_id }}&amp;step=dtmf_urgent">
    <Play>{{ urgent_repeat_url }}</Play>
  </Gather>
  <Play>{{ no_input_url }}</Play>
  <Hangup/>
</Response>""")

_FLOW_C_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ wellness_greeting_url }}</Play>
  <Gather numDigits="1" timeout="10"
          action="{{ webhook_base }}/ivr/webhook/exotel?call_id={{ call_id }}&amp;step=dtmf_wellness">
    <Play>{{ wellness_options_url }}</Play>
  </Gather>
  <Play>{{ no_input_url }}</Play>
  <Hangup/>
</Response>""")

_FLOW_C_SYMPTOM_TEMPLATE = _env.from_string("""\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{{ symptom_prompt_url }}</Play>
  <Gather numDigits="1" timeout="10"
          action="{{ webhook_base }}/ivr/webhook/exotel?call_id={{ call_id }}&amp;step=dtmf_symptom">
    <Play>{{ symptom_options_url }}</Play>
  </Gather>
  <Play>{{ no_input_url }}</Play>
  <Hangup/>
</Response>""")

# --------------------------------------------------------------------------- #
# Script registry — maps script_id to (template, language)
# --------------------------------------------------------------------------- #

# TTS strings by flow and language
TTS_STRINGS: dict[str, dict[str, str]] = {
    "ta": {
        "flowA_prompt": (
            "வணக்கம்! நீங்கள் உங்கள் மருந்தை எடுத்தீர்களா? எடுத்திருந்தால் 1 ஐ அழுத்தவும், தவிர்க்க 2 ஐ அழுத்தவும்."
        ),
        "flowA_repeat": ("மருந்து எடுத்திருந்தால் 1 ஐ அழுத்தவும்."),
        "flowA_confirm": "நன்று! உங்கள் மருந்து பதிவு செய்யப்பட்டது. நன்றி!",
        "flowA_skip": "சரி, நீங்கள் இந்த மருந்தை தவிர்த்தீர்கள் என்று பதிவு செய்யப்பட்டது.",
        "flowA_no_input": "நாங்கள் பின்னர் திரும்ப அழைப்போம். நன்றி!",
        "flowB_urgent": (
            "அவசர அறிவிப்பு! உங்கள் மருந்தை உடனடியாக எடுக்கவும். "
            "உங்கள் குடும்பத்தினருக்கு தெரிவிக்கப்பட்டுள்ளது. "
            "உதவிக்கு 1 ஐ அழுத்தவும்."
        ),
        "flowB_repeat": "உதவிக்கு 1 ஐ அழுத்தவும்.",
        "flowC_greeting": (
            "வணக்கம்! இன்று உங்கள் உடல்நலம் எப்படி உள்ளது? "
            "நன்றாக இருந்தால் 1, ஏதாவது உடல் கோளாறு இருந்தால் 2, "
            "மருத்துவரை அழைக்க 3 ஐ அழுத்தவும்."
        ),
        "flowC_options": "நன்றாக இருந்தால் 1, பிரச்சனை இருந்தால் 2 அழுத்தவும்.",
        "flowC_symptom": (
            "எந்த அறிகுறி உள்ளது? தலைவலி 1, வயிற்று வலி 2, தலைசுற்றல் 3, வேறு 4 ஐ அழுத்தவும்."
        ),
        "flowC_symptom_options": "உங்கள் அறிகுறியை தேர்ந்தெடுக்கவும்.",
    },
    "hi": {
        "flowA_prompt": ("नमस्ते! क्या आपने अपनी दवाई ली? हाँ तो 1 दबाएं, छोड़ना है तो 2 दबाएं।"),
        "flowA_repeat": "दवाई ली हो तो 1 दबाएं।",
        "flowA_confirm": "बहुत अच्छा! आपकी दवाई दर्ज हो गई। धन्यवाद!",
        "flowA_skip": "ठीक है, इस दवाई को छोड़ा हुआ दर्ज कर दिया गया है।",
        "flowA_no_input": "हम बाद में वापस फोन करेंगे। धन्यवाद!",
        "flowB_urgent": (
            "तत्काल सूचना! कृपया अभी अपनी दवाई लें। आपके परिवार को सूचित किया गया है। सहायता के लिए 1 दबाएं।"
        ),
        "flowB_repeat": "सहायता के लिए 1 दबाएं।",
        "flowC_greeting": (
            "नमस्ते! आज आप कैसे हैं? अच्छे हैं तो 1, कोई तकलीफ है तो 2, डॉक्टर से बात करनी है तो 3 दबाएं।"
        ),
        "flowC_options": "अच्छे हैं तो 1, तकलीफ है तो 2 दबाएं।",
        "flowC_symptom": ("क्या तकलीफ है? सिरदर्द 1, पेटदर्द 2, चक्कर आना 3, कुछ और 4 दबाएं।"),
        "flowC_symptom_options": "अपनी तकलीफ चुनें।",
    },
    "en": {
        "flowA_prompt": ("Hello! Did you take your medication? Press 1 for yes, press 2 to skip."),
        "flowA_repeat": "Press 1 if you took your medication.",
        "flowA_confirm": "Great! Your medication has been recorded. Thank you!",
        "flowA_skip": "Okay, this dose has been recorded as skipped.",
        "flowA_no_input": "We will call back later. Thank you!",
        "flowB_urgent": (
            "URGENT notice! Please take your medication immediately. "
            "Your family has been notified. Press 1 for assistance."
        ),
        "flowB_repeat": "Press 1 for assistance.",
        "flowC_greeting": (
            "Hello! How are you feeling today? "
            "Press 1 if you are well, press 2 if you have any discomfort, "
            "press 3 to speak to a doctor."
        ),
        "flowC_options": "Press 1 if well, press 2 if there is a problem.",
        "flowC_symptom": (
            "What symptom do you have? Headache press 1, stomach pain press 2, "
            "dizziness press 3, other press 4."
        ),
        "flowC_symptom_options": "Please select your symptom.",
    },
}


def render_flow_a(call_id: str, language: str, webhook_base: str) -> str:
    from app.ivr.tts import get_tts_url

    strings = TTS_STRINGS.get(language, TTS_STRINGS["en"])
    return _FLOW_A_TEMPLATE.render(
        call_id=call_id,
        webhook_base=webhook_base,
        prompt_url=get_tts_url(strings["flowA_prompt"], language, call_id=call_id),
        repeat_url=get_tts_url(strings["flowA_repeat"], language, call_id=call_id),
        no_input_url=get_tts_url(strings["flowA_no_input"], language, call_id=call_id),
    )


def render_flow_a_dtmf(call_id: str, language: str, dtmf: str) -> str:
    from app.ivr.tts import get_tts_url

    strings = TTS_STRINGS.get(language, TTS_STRINGS["en"])
    if dtmf == "1":
        return _FLOW_A_DTMF1_TEMPLATE.render(
            confirm_url=get_tts_url(strings["flowA_confirm"], language, call_id=call_id)
        )
    return _FLOW_A_DTMF2_TEMPLATE.render(
        skip_ack_url=get_tts_url(strings["flowA_skip"], language, call_id=call_id)
    )


def render_flow_b(call_id: str, language: str, webhook_base: str) -> str:
    from app.ivr.tts import get_tts_url

    strings = TTS_STRINGS.get(language, TTS_STRINGS["en"])
    return _FLOW_B_TEMPLATE.render(
        call_id=call_id,
        webhook_base=webhook_base,
        urgent_prompt_url=get_tts_url(strings["flowB_urgent"], language, call_id=call_id),
        urgent_repeat_url=get_tts_url(strings["flowB_repeat"], language, call_id=call_id),
        no_input_url=get_tts_url(strings["flowA_no_input"], language, call_id=call_id),
    )


def render_flow_c(call_id: str, language: str, webhook_base: str) -> str:
    from app.ivr.tts import get_tts_url

    strings = TTS_STRINGS.get(language, TTS_STRINGS["en"])
    return _FLOW_C_TEMPLATE.render(
        call_id=call_id,
        webhook_base=webhook_base,
        wellness_greeting_url=get_tts_url(strings["flowC_greeting"], language, call_id=call_id),
        wellness_options_url=get_tts_url(strings["flowC_options"], language, call_id=call_id),
        no_input_url=get_tts_url(strings["flowA_no_input"], language, call_id=call_id),
    )


def render_flow_c_symptom(call_id: str, language: str, webhook_base: str) -> str:
    from app.ivr.tts import get_tts_url

    strings = TTS_STRINGS.get(language, TTS_STRINGS["en"])
    return _FLOW_C_SYMPTOM_TEMPLATE.render(
        call_id=call_id,
        webhook_base=webhook_base,
        symptom_prompt_url=get_tts_url(strings["flowC_symptom"], language, call_id=call_id),
        symptom_options_url=get_tts_url(
            strings["flowC_symptom_options"], language, call_id=call_id
        ),
        no_input_url=get_tts_url(strings["flowA_no_input"], language, call_id=call_id),
    )


SCRIPT_RENDERERS: dict[str, Any] = {
    "flowA_tamil": lambda call_id, **kw: render_flow_a(call_id, "ta", kw["webhook_base"]),
    "flowA_hindi": lambda call_id, **kw: render_flow_a(call_id, "hi", kw["webhook_base"]),
    "flowA_english": lambda call_id, **kw: render_flow_a(call_id, "en", kw["webhook_base"]),
    "flowB_tamil": lambda call_id, **kw: render_flow_b(call_id, "ta", kw["webhook_base"]),
    "flowB_hindi": lambda call_id, **kw: render_flow_b(call_id, "hi", kw["webhook_base"]),
    "flowB_english": lambda call_id, **kw: render_flow_b(call_id, "en", kw["webhook_base"]),
    "flowC_hindi": lambda call_id, **kw: render_flow_c(call_id, "hi", kw["webhook_base"]),
    "flowC_tamil": lambda call_id, **kw: render_flow_c(call_id, "ta", kw["webhook_base"]),
    "flowC_english": lambda call_id, **kw: render_flow_c(call_id, "en", kw["webhook_base"]),
}
