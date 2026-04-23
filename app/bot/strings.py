"""All user-facing text for the Telegram bot. No hardcoded strings elsewhere."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "hi": {
        "welcome": ("नमस्ते! 🙏\nमैं *Saath* हूँ — आपकी दवाइयों का साथी।\nकृपया अपनी भाषा चुनें:"),
        "ask_name": "आपका नाम क्या है? ✍️",
        "ask_conditions": (
            "आपको कौन-कौन सी बीमारियाँ हैं? (एक से ज़्यादा चुन सकते हैं)\nचुनने के बाद *Done* दबाएँ।"
        ),
        "condition_diabetes": "मधुमेह (Diabetes)",
        "condition_bp": "रक्तचाप (BP)",
        "condition_thyroid": "थायरॉइड",
        "condition_ckd": "किडनी (CKD)",
        "condition_heart": "हृदय (Heart)",
        "condition_other": "अन्य",
        "done_btn": "✅ आगे बढ़ें",
        "ask_med_name": "दवाई का नाम लिखें।\nजैसे: Metformin 500mg",
        "ask_med_dose": "कितनी मात्रा (dose)? अगर नहीं पता तो *Skip* दबाएँ।",
        "skip_btn": "Skip / कोई नहीं",
        "ask_med_frequency": "दिन में कितनी बार? कृपया समय चुनें:",
        "timing_morning": "☀️ सुबह",
        "timing_afternoon": "🌤 दोपहर",
        "timing_evening": "🌆 शाम",
        "timing_night": "🌙 रात",
        "ask_med_timing": "समय चुनें। एक से ज़्यादा चुन सकते हैं। फिर *Done* दबाएँ।",
        "med_added": "दवाई जोड़ दी गई ✅\n*{drug}* — {timings}",
        "add_more_btn": "➕ और दवाई जोड़ें",
        "no_more_btn": "✅ बस, आगे बढ़ें",
        "confirm_profile": (
            "यह जानकारी सही है?\n\n👤 नाम: *{name}*\n🩺 बीमारियाँ: {conditions}\n\n💊 दवाइयाँ:\n{meds}"
        ),
        "edit_btn": "✏️ शुरू से बदलें",
        "confirm_btn": "✅ सही है",
        "onboarding_done": (
            "बहुत बढ़िया! 🎉\nमैं आपको हर दवाई के समय याद दिलाऊँगा।\nअगली याद: *{next_time}*"
        ),
        "reminder_header": ("नमस्ते {name} 🙏\n*{timing}* की दवाई का समय हो गया है:\n💊 *{drug}*"),
        "took_btn": "✅ ले ली",
        "snooze_btn": "⏰ 30 मिनट बाद",
        "skip_btn_reminder": "❌ आज नहीं",
        "took_confirm": "शाबाश! ✅ दवाई लेने का रिकॉर्ड हो गया।",
        "snooze_confirm": "ठीक है, 30 मिनट बाद फिर याद दिलाऊँगा ⏰",
        "skip_confirm": "ठीक है, आज की *{timing}* की दवाई छोड़ दी।",
        "snooze_exhausted": ("आपने दो बार snooze कर लिया है। इस दवाई को *skip* मान लिया गया है।"),
        "daily_summary_header": "📋 आज का रिपोर्ट — {date}\n",
        "daily_summary_taken": "✅ ली गई: {count}",
        "daily_summary_skipped": "❌ छोड़ी गई: {count}",
        "daily_summary_missed": "⚠️ छूट गई: {count}",
        "status_reply": (
            "👤 *{name}*\n"
            "🩺 {conditions}\n\n"
            "💊 दवाइयाँ: {med_count}\n"
            "📊 आज: ✅ {taken}  ❌ {skipped}  ⚠️ {missed}"
        ),
        "already_registered": (
            "आप पहले से रजिस्टर्ड हैं 🙏\n/status — आज की रिपोर्ट\n/edit — जानकारी बदलें"
        ),
        "unknown_message": ("माफ़ कीजिए, मुझे समझ नहीं आया।\n/status — रिपोर्ट देखें\n/edit — जानकारी बदलें"),
        "timing_label_morning": "सुबह",
        "timing_label_afternoon": "दोपहर",
        "timing_label_evening": "शाम",
        "timing_label_night": "रात",
        "reset_done": "सारी जानकारी मिटा दी गई। /start दबाकर फिर शुरू करें।",
    },
    "ta": {
        "welcome": ("வணக்கம்! 🙏\nநான் *Saath* — உங்கள் மருந்து நண்பன்.\nஉங்கள் மொழியை தேர்ந்தெடுக்கவும்:"),
        "ask_name": "உங்கள் பெயர் என்ன? ✍️",
        "ask_conditions": (
            "உங்களுக்கு என்ன நோய்கள் உள்ளன? (ஒன்றுக்கு மேல் தேர்வு செய்யலாம்)\nமுடித்ததும் *Done* அழுத்தவும்."
        ),
        "condition_diabetes": "சர்க்கரை நோய் (Diabetes)",
        "condition_bp": "இரத்த அழுத்தம் (BP)",
        "condition_thyroid": "தைராய்டு",
        "condition_ckd": "சிறுநீரகம் (CKD)",
        "condition_heart": "இதயம் (Heart)",
        "condition_other": "மற்றவை",
        "done_btn": "✅ தொடரவும்",
        "ask_med_name": "மருந்தின் பெயரை எழுதவும்.\nஉதா: Metformin 500mg",
        "ask_med_dose": "என்ன அளவு (dose)? தெரியவில்லை என்றால் *Skip* அழுத்தவும்.",
        "skip_btn": "Skip / இல்லை",
        "ask_med_frequency": "ஒரு நாளைக்கு எத்தனை முறை? நேரத்தைத் தேர்ந்தெடுக்கவும்:",
        "timing_morning": "☀️ காலை",
        "timing_afternoon": "🌤 மதியம்",
        "timing_evening": "🌆 மாலை",
        "timing_night": "🌙 இரவு",
        "ask_med_timing": "நேரங்களைத் தேர்ந்தெடுக்கவும். பின்பு *Done* அழுத்தவும்.",
        "med_added": "மருந்து சேர்க்கப்பட்டது ✅\n*{drug}* — {timings}",
        "add_more_btn": "➕ மேலும் மருந்து",
        "no_more_btn": "✅ போதும், தொடரவும்",
        "confirm_profile": (
            "இந்தத் தகவல் சரிதானா?\n\n👤 பெயர்: *{name}*\n🩺 நோய்கள்: {conditions}\n\n💊 மருந்துகள்:\n{meds}"
        ),
        "edit_btn": "✏️ மீண்டும் தொடங்கு",
        "confirm_btn": "✅ சரி",
        "onboarding_done": (
            "அருமை! 🎉\n"
            "ஒவ்வொரு மருந்தின் நேரத்திலும் உங்களுக்கு நினைவூட்டுவேன்.\n"
            "அடுத்த நினைவூட்டல்: *{next_time}*"
        ),
        "reminder_header": ("வணக்கம் {name} 🙏\n*{timing}* மருந்து நேரம் வந்துவிட்டது:\n💊 *{drug}*"),
        "took_btn": "✅ எடுத்துக்கொண்டேன்",
        "snooze_btn": "⏰ 30 நிமிடத்தில்",
        "skip_btn_reminder": "❌ இன்று வேண்டாம்",
        "took_confirm": "நன்று! ✅ பதிவு செய்யப்பட்டது.",
        "snooze_confirm": "சரி, 30 நிமிடம் கழித்து மீண்டும் நினைவூட்டுகிறேன் ⏰",
        "skip_confirm": "சரி, இன்றைய *{timing}* மருந்து தவிர்க்கப்பட்டது.",
        "snooze_exhausted": (
            "நீங்கள் இரண்டு முறை snooze செய்துவிட்டீர்கள். இந்த மருந்து *skip* ஆக பதிவு செய்யப்பட்டது."
        ),
        "daily_summary_header": "📋 இன்றைய அறிக்கை — {date}\n",
        "daily_summary_taken": "✅ எடுத்தது: {count}",
        "daily_summary_skipped": "❌ தவிர்த்தது: {count}",
        "daily_summary_missed": "⚠️ விடப்பட்டது: {count}",
        "status_reply": (
            "👤 *{name}*\n"
            "🩺 {conditions}\n\n"
            "💊 மருந்துகள்: {med_count}\n"
            "📊 இன்று: ✅ {taken}  ❌ {skipped}  ⚠️ {missed}"
        ),
        "already_registered": (
            "நீங்கள் ஏற்கனவே பதிவு செய்துள்ளீர்கள் 🙏\n/status — இன்றைய அறிக்கை\n/edit — தகவலை மாற்ற"
        ),
        "unknown_message": ("மன்னிக்கவும், புரியவில்லை.\n/status — அறிக்கை\n/edit — தகவலை மாற்ற"),
        "timing_label_morning": "காலை",
        "timing_label_afternoon": "மதியம்",
        "timing_label_evening": "மாலை",
        "timing_label_night": "இரவு",
        "reset_done": "அனைத்து தகவலும் நீக்கப்பட்டது. /start அழுத்தி மீண்டும் தொடங்கவும்.",
    },
    "en": {
        "welcome": (
            "Hello! 🙏\nI'm *Saath* — your medication companion.\nPlease pick your language:"
        ),
        "ask_name": "What is your name? ✍️",
        "ask_conditions": (
            "Which conditions do you have? (You can pick more than one.)\nTap *Done* when finished."
        ),
        "condition_diabetes": "Diabetes",
        "condition_bp": "Blood Pressure",
        "condition_thyroid": "Thyroid",
        "condition_ckd": "Kidney (CKD)",
        "condition_heart": "Heart",
        "condition_other": "Other",
        "done_btn": "✅ Done",
        "ask_med_name": "Enter medication name.\ne.g. Metformin 500mg",
        "ask_med_dose": "What dose? Tap *Skip* if unsure.",
        "skip_btn": "Skip",
        "ask_med_frequency": "How many times a day? Pick the timings:",
        "timing_morning": "☀️ Morning",
        "timing_afternoon": "🌤 Afternoon",
        "timing_evening": "🌆 Evening",
        "timing_night": "🌙 Night",
        "ask_med_timing": "Pick timings. Multiple allowed. Then *Done*.",
        "med_added": "Medication added ✅\n*{drug}* — {timings}",
        "add_more_btn": "➕ Add more",
        "no_more_btn": "✅ Done adding",
        "confirm_profile": (
            "Is this correct?\n\n"
            "👤 Name: *{name}*\n"
            "🩺 Conditions: {conditions}\n\n"
            "💊 Medications:\n{meds}"
        ),
        "edit_btn": "✏️ Edit from start",
        "confirm_btn": "✅ Confirm",
        "onboarding_done": (
            "All set! 🎉\nI'll remind you at every dose time.\nNext reminder: *{next_time}*"
        ),
        "reminder_header": ("Hi {name} 🙏\nTime for your *{timing}* dose:\n💊 *{drug}*"),
        "took_btn": "✅ Took it",
        "snooze_btn": "⏰ 30 min later",
        "skip_btn_reminder": "❌ Not today",
        "took_confirm": "Well done! ✅ Logged.",
        "snooze_confirm": "Okay, I'll remind you again in 30 minutes ⏰",
        "skip_confirm": "Okay, skipped your *{timing}* dose for today.",
        "snooze_exhausted": ("You've snoozed twice. This dose is now marked as *skipped*."),
        "daily_summary_header": "📋 Today's report — {date}\n",
        "daily_summary_taken": "✅ Taken: {count}",
        "daily_summary_skipped": "❌ Skipped: {count}",
        "daily_summary_missed": "⚠️ Missed: {count}",
        "status_reply": (
            "👤 *{name}*\n"
            "🩺 {conditions}\n\n"
            "💊 Medications: {med_count}\n"
            "📊 Today: ✅ {taken}  ❌ {skipped}  ⚠️ {missed}"
        ),
        "already_registered": (
            "You're already registered 🙏\n/status — today's report\n/edit — update info"
        ),
        "unknown_message": ("Sorry, I didn't understand.\n/status — report\n/edit — update info"),
        "timing_label_morning": "morning",
        "timing_label_afternoon": "afternoon",
        "timing_label_evening": "evening",
        "timing_label_night": "night",
        "reset_done": "All data cleared. Tap /start to begin again.",
    },
}


def get_string(key: str, lang: str, **kwargs: str | int) -> str:
    """Return STRINGS[lang][key] formatted with kwargs. Falls back to 'en'."""
    lang = lang if lang in STRINGS else "en"
    template = STRINGS.get(lang, {}).get(key)
    if template is None:
        template = STRINGS["en"].get(key, key)
    if not template:
        return key
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template


def timing_label(timing: str, lang: str) -> str:
    return get_string(f"timing_label_{timing}", lang)
