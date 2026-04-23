**PRODUCT REQUIREMENTS DOCUMENT**

साथ  **Saath**

*AI Medical Companion for Aging Indian Parents — built for the children who live far from home.*

| Field | Value |
| :---- | :---- |
| Product | Saath ("together" in Hindi/Urdu) |
| Author | Naman Goyal (PM / Builder) |
| Document version | v3.1 — Final. Integrates v2.2 IVR (§4.6) and Doctor Visit Report (§4.7) into the v3.0 pivoted architecture. |
| Date | April 22, 2026 |
| Status | LOCKED FOR BUILD |
| Hackathon target | Built with Opus 4.7 · April 26, 2026 · 8:00 PM EST |
| Model | Claude Opus 4.7 (1M context, 2,576 px vision, extended thinking, Managed Agents) |
| Supersedes | Saath\_PRD\_v2\_2\_DoctorReport.docx · Saath\_PRD\_v3\_0\_Final.docx |

# **1\. Executive summary**

Saath is an AI health companion for Indian seniors aging alone and the NRI or metro adult children who care for them from a distance. The senior (Lakshmi, 71, Bengaluru) gets medication reminders in Tamil via Telegram, receives IVR voice calls when she misses a dose, answers wellness checks on her phone keypad, and never installs an app. The adult child (Priya, 34, San Jose) gets a daily one-paragraph brief, live anomaly alerts, and a clinician-grade Doctor Visit Report she can send her mother's GP ahead of every appointment.

The product sits in a genuine three-way white space: longitudinal lab/medication reasoning (Opus 4.7 1M context) \+ culturally-native voice/TTS (Tamil, Hindi, Hinglish) \+ clinician-facing synthesis (the Doctor Visit Report). ElliQ covers the voice companion, Ultrahuman the labs, Emoha the human-concierge daughter-call — none combine all three, and none produce a physician-ready PDF that turns a 'theek hoon, Doctor sahab' appointment into a clinically productive 20 minutes.

Technically, the voice loop is a dual-model router: Claude Haiku 4.5 handles conversational turn-taking (\~600–1,000 ms), and Claude Opus 4.7 runs as a background tool call for deep reasoning — lab interpretation, DDI checks via extended thinking, longitudinal synthesis, and Doctor Visit Report generation — using its 1M context window, 2,576 px vision, memory\_20250818 tool, xhigh thinking effort, and a supervisor/sub-agent fan-out architecture.

| Commitment one-liner Claude Opus 4.7 as the 24/7 AI health companion for India's aging parents and the NRI children who can't be there — every day a brief, every missed dose a call, every appointment a report. |
| :---- |
| **What's new in v3.1** (a) §6.6 adds the complete three-flow IVR specification (missed-medication escalation, URGENT anomaly voice alert, Priya-triggered wellness check) with scripts, DTMF trees, and telephony spec — ported from v2.2 §4.6. (b) §6.7 adds the complete Doctor Visit Report specification — content schema, the 12-step agent generation flow, specialist-tailored variants (GP/Nephro/Endo/Cardio/Emergency), sample executive summary, and five delivery options — ported from v2.2 §4.7. (c) Primary persona reconciled to Lakshmi Iyer \+ Priya Iyer (v2.2) to match the detailed clinical scenarios these flows reference. Meera Sharma is retained as a Synthea test persona. (d) Telephony locked to Exotel (India) \+ Twilio (US/global), per v2.2 validation. Plivo retained as India backup. |

# **2\. Problem & opportunity**

## **2.1 The Cross-Border Elder Care Information Vacuum**

32 million NRI and diaspora adults are the de-facto care managers for aging Indian parents they cannot see daily. A further \~40 million metro-resident Indian adult children are in the same structural position — a Bengaluru-based daughter checking on her Chennai-based mother is separated by the same information vacuum as one in San Jose. The problem isn't love; it's information architecture.

## **2.2 Four compounding failures**

| \# | Failure | Why it kills |
| :---- | :---- | :---- |
| 1 | Lab reports go unread as a longitudinal series | A senior with diabetes, hypertension, and early CKD accumulates 4–8 lab panels/year across Thyrocare, Dr Lal, Metropolis, SRL. No human reads them as a trend. A slow eGFR decline of 78→71→65→58 gets caught months after it should — sometimes after irreversible harm. |
| 2 | Polypharmacy errors compound silently | Seniors with 3+ chronic conditions take 5–10 medications across multiple specialists who don't share records. Drug-drug interactions, drug-renal mismatches (Metformin in declining kidney function), and dose-timing errors are routine. No single agent watches the whole picture. |
| 3 | The adult child has no signal | Sunday calls don't catch what continuous monitoring sees. The child gets a flood of forwarded WhatsApp photos of prescriptions and lab reports they can't interpret, and no signal that says 'your parent is fine today' or 'your parent needs attention now.' |
| 4 | Incumbent eldercare is expensive and thin on insight | Emoha, Samarth, KITES, Anvayaa charge ₹8,000–₹1,20,000/month for in-person visits and concierge calling, with thin AI layers. NRIs already spend 5–10× our $30/month price — willingness to pay is proven. What's missing is the AI-native product layer. |

## **2.3 Why now**

* Claude Opus 4.7 ships a 1M-token context window, 2,576 px vision, the memory tool (memory\_20250818), xhigh thinking effort, and Managed Agents — the first model that can hold a senior's multi-year health story in one reasoning pass and orchestrate four specialist sub-agents in parallel.

* Sarvam Saaras v3 / Bulbul v3 and Google Cloud Neural2 Indic voices make Hindi and Tamil TTS finally feel native to a 71-year-old.

* India's DPDPA 2023 \+ CDSCO October 2025 SaMD draft guidance define a narrow but usable general-wellness safe harbour — provided every clinical output is framed as 'informational summary, physician review recommended,' never prescriptive.

# **3\. Target audience & personas**

## **3.1 Audience matrix**

| Role | Who | Where | What they need from Saath |
| :---- | :---- | :---- | :---- |
| Primary paying user | Adult child of Indian senior, 30–45 | US, UAE, UK, Singapore, Canada, Australia \+ Indian metros | One-paragraph daily signal: "Mom is fine / needs attention." One tap to act. |
| End user (beneficiary) | Indian senior, 60–85 | India Tier-1/2 cities | Medication reminders in their language. Never has to learn a new app. |
| Phase 3 (future) | Treating physician | India | Retainer-panel dashboard with AI-pre-read summaries and sign-off workflow. |
| Phase 4 (future) | Insurance / corporate | India \+ global | B2B2C via NRI corporate benefits bundles. |

## **3.2 Primary personas**

### **Persona A — Lakshmi Iyer (the parent, end user)**

| Attribute | Detail |
| :---- | :---- |
| Age / gender | 71, female |
| Location | HSR Layout, Bengaluru |
| Languages | Tamil (native), Hindi (functional, warmer register for casual check-ins), English (passable) |
| Tech comfort | Smartphone owner; uses WhatsApp daily; has never installed an app herself |
| Conditions | Type 2 Diabetes (12 yrs) · Hypertension (8 yrs) · Hypothyroidism (5 yrs) · CKD Stage 3a (eGFR 58, declining) |
| Medications (7) | Metformin 1000 mg BD · Glimepiride 2 mg OD · Telmisartan 40 mg OD · Amlodipine 5 mg OD · Atorvastatin 20 mg HS · Levothyroxine 75 mcg fasting · Vitamin D3 60K weekly |
| Labs (last 4 quarters) | eGFR 78 → 71 → 65 → 58  ·  HbA1c 7.2 → 7.4 → 7.6 → 7.8  ·  Creatinine 0.9 → 1.0 → 1.1 → 1.2  ·  TSH stable at 2.0–2.4 |
| Physicians | Dr. Sharma (GP, monthly) · Nephrologist (quarterly) · Endocrinologist (6-monthly) |

### **Persona B — Priya Iyer (the NRI daughter, primary paying user)**

| Attribute | Detail |
| :---- | :---- |
| Age / gender | 34, female |
| Location | San Jose, California (9,000 miles from her mother) |
| Profession | Software PM at a FAANG, married, one child |
| Visits home | 3 weeks/year (one long December visit \+ one emergency visit usually) |
| Current spend on care | \~$150–$400/month — Emoha-like concierge, scattered medication refills, weekend travel for emergencies |
| Clinical literacy | High-agency and technical; not clinical. Can read a lab report but can't interpret a multi-quarter trend. Carries continuous low-grade anxiety about her mother between visits. |
| Willingness to pay | $30/month for a meaningful daily signal — proven benchmark against Emoha at 5–10×. |

### **Persona C — Meera Sharma (Synthea test persona)**

A second Synthea-generated persona used for eval: Meera, 68, Delhi, Hindi-primary, milder comorbidities (T2D \+ HTN only, no CKD). Used to validate that the flows generalize beyond Lakshmi's specific clinical picture.

## **3.3 Out of scope for v1**

* Young-adult preventive / biohacker users (Function Health, Ultrahuman Blood Vision, Superpower own this).

* Hospital-to-patient workflows (Hippocratic AI Front Door territory).

* Seniors without any adult child as guardian — the brief and report loops are load-bearing for retention and pricing.

# **4\. Positioning & competitive landscape**

| Competitor | Voice-first in Hindi/Tamil | Longitudinal lab/DDI depth | NRI-child brief / doctor report | Wellness-safe framing | All 3 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Saath | Yes | Yes | Yes | Yes | ✓ |
| ElliQ (Intuition Robotics) | Yes (English) | No | Partial | Yes | — |
| HealthifyMe Ria | Partial (English) | No | No | Partial | — |
| Ultrahuman / Superpower | No | Yes | No | Partial | — |
| Emoha Daughter | Yes (human) | No | Yes | Yes | — |
| Hippocratic AI Front Door | Yes (English) | Partial | No | Clinical (SaMD) | — |

## **4.1 One-line rebuttals (for the pitch)**

* **vs Hippocratic AI:** "Hippocratic is the hospital-to-patient front door; Saath is the patient-to-family continuous companion, language-native for India's 50M aging-alone parents."

* **vs HealthifyMe Ria:** "Ria is 60 seconds of English preventive chat for 30-year-olds; Saath is a five-year Tamil/Hindi memory for 71-year-olds and their NRI daughters."

* **vs Emoha:** "Emoha validated $30 × 5–10 willingness-to-pay for a daughter-call service; Saath replaces the human caller with an AI — so the unit economics actually work at scale."

# **5\. Goals & non-goals**

## **5.1 Product goals (v1 — hackathon)**

1. Ship a working senior ↔ Saath medication-reminder and IVR loop in Tamil and Hindi with ≤1s median hot-path turn latency and a live outbound call during the demo.

2. Demonstrate Opus 4.7's 1M context on Lakshmi's 4-quarter lab history: correctly thread eGFR 78 → 71 → 65 → 58 as a declining trend and flag it.

3. Ingest a real Indian lab PDF (Thyrocare, Dr Lal, Metropolis, or SRL) via Opus 4.7 vision and produce a structured JSON biomarker extraction with units and ref ranges in ≤8 seconds.

4. Run a live DDI extended-thinking trace: Metformin-renal flag \+ Amlodipine \+ Telmisartan → orthostatic hypotension correlation visible on screen.

5. Generate a Doctor Visit Report PDF for Lakshmi's next GP appointment with all 10 schema sections filled, the 3-sentence physician executive summary on page 1, and specialist-variant switching demonstrated.

6. Deliver the daily brief to Priya's real Telegram during judging — a live message lands, not a screenshot.

7. Earn the 25% "Opus 4.7 Use" judging weight by explicitly demoing: 1M context · 2,576 px vision · xhigh extended thinking · memory tool · managed-agents fan-out · MCP-Atlas tool orchestration · Claude Code subagents.

## **5.2 Non-goals**

* Disease prediction, diagnosis, or screening language. Every clinical output carries 'informational summary, physician review recommended.' Descriptive and suggestive, never prescriptive.

* Cancer risk scoring (CDSCO Class C landmine since Nov 2025).

* Real WhatsApp Business API integration inside the 5-day build window (1–3 week approval); demo uses Telegram \+ SMS, WhatsApp path shown via screenshot mock.

* Live wearable integration (Galaxy Watch in Phase 2; Phase 1 uses simulated vitals fixture).

* Clinician-facing sign-off workflow (Phase 3).

# **6\. Product requirements**

## **6.1 R1 — Senior voice & messaging loop (Telegram primary)**

### **Functional requirements**

* R1.1 The senior receives medication reminders via Telegram bot in her chosen language (Tamil / Hindi / English) with emoji \+ large text and no nested menus.

* R1.2 Reminder buttons: ✅ Took it · ⏰ Snooze 15 min · ⏭ Skip (with reason).

* R1.3 Each reminder has a 2-snooze cap; on second snooze expiry the auto-Skip fires at \+45 minutes and triggers IVR escalation (§6.6.1).

* R1.4 Free-text inbound messages ("I feel dizzy after my morning tablets") are logged to the Telegram inbound store and routed to the SymptomSubAgent for next-brief inclusion.

* R1.5 TTS hot path uses Sarvam Bulbul v3 for Hindi and Google Cloud Neural2 (ta-IN-Neural2-A) for Tamil; STT uses Sarvam Saaras v3 (mode=codemix) for Hinglish and Google Cloud STT for Tamil.

### **Acceptance criteria**

* AC1.1 Hindi and Tamil reminder flows each complete end-to-end under 1.2 s median turn latency in the demo.

* AC1.2 A snooze → auto-Skip → IVR escalation chain fires and is logged end-to-end in the compliance record.

## **6.2 R2 — Longitudinal memory (multi-year story)**

* R2.1 Per-user filesystem-backed memory: /memories/{user\_id}/profile.md · labs/\*.json · visits/\*.md · daily\_summary/\*.md · transcripts/ivr/\*.md · consent.json.

* R2.2 Wired to Opus 4.7 via memory\_20250818 tool \+ context-management-2025-06-27 beta header.

* R2.3 On every voice/chat turn, the Haiku orchestrator loads the user's profile.md and last 14 daily\_summary entries (\~8–12K tokens).

* R2.4 On longitudinal queries ("compared to last year," "since October," "am I getting better") the orchestrator invokes deep\_health\_analysis(user\_id, trigger), which assembles multi-year context (up to the 1M window) and calls Opus 4.7 with effort: "xhigh" and thinking: {display: "summarized"}.

### **Acceptance criteria**

* AC2.1 Lakshmi's eGFR 78 → 71 → 65 → 58 trend is threaded across all 4 quarterly panels in one Opus pass with the decline rate computed and flagged.

* AC2.2 Agent never re-introduces itself to a returning user — memory tool demonstrably persists identity across sessions.

## **6.3 R3 — Lab & wearable ingestion**

* R3.1 Priya drops a lab PDF onto the dashboard → POST /lab-pdf → Opus 4.7 vision at 2,576 px / 300 DPI extracts structured JSON: { biomarker, value, unit, ref\_range\_low, ref\_range\_high, flag, collection\_date, lab\_chain } in ≤8 seconds.

* R3.2 Fallback: pdfplumber text extraction if Opus vision confidence \<0.85 mean per field.

* R3.3 Wearable (Phase 2): Galaxy Watch 4+ via Samsung Health Data SDK. Phase 1 uses a deterministic fixture emitting the same schema so agent contracts are forward-compatible.

### **Acceptance criteria**

* AC3.1 A real Thyrocare/Dr Lal sample PDF parses with ≥90% biomarker accuracy on a hand-labeled 50-biomarker eval.

* AC3.2 A Galaxy-Watch-shaped fixture payload is ingested and rolled into the daily\_summary unchanged between Phase 1 and Phase 2\.

## **6.4 R4 — DDI (drug-drug interaction) reasoning**

Polypharmacy is the silent killer in Indian eldercare. The DDIAgent uses Opus 4.7 extended thinking to reason step-by-step through Lakshmi's 7-drug regimen before surfacing any flag. This is not a lookup table; it is pharmacological reasoning.

* R4.1 On every new lab or new prescription, the DDIAgent runs with effort: "xhigh" and thinking: {display: "summarized"}.

* R4.2 The thinking trace is captured and surfaced in the demo dashboard.

* R4.3 Flag levels: LOW (informational) · MEDIUM (physician should know) · HIGH (flag on brief) · URGENT (IVR escalation per §6.6.2).

* R4.4 Canonical demo flags: (a) Metformin \+ eGFR 55 approaching the 45 dose-review threshold → HIGH; (b) Amlodipine \+ Telmisartan \+ morning-dose dizziness → orthostatic hypotension, elevated from MEDIUM to HIGH after 3 symptom corroborations.

## **6.5 R5 — Daily brief for the NRI child**

* R5.1 Every morning at Priya's 08:00 local, the ManagedAgent synthesizes the past 24 hours (medication adherence \+ any IVR events \+ any new symptoms \+ any new labs \+ any DDI flags) into a one-paragraph Telegram message.

* R5.2 Brief quality bar: ≤180 words · references ≥5 distinct data sources · ends with a single concrete next action sized for ≤10 minutes · no alarmist language · no dosage suggestions.

* R5.3 URGENT escalations do not wait for the morning brief; they page Priya immediately (§6.6.2).

* R5.4 Granular consent: per-recipient, per-category, per-time-window. Lakshmi can voice-command "Priya ko lab reports mat bhejo" and the next brief excludes labs.

## **6.6 R6 — IVR (voice call) flows**

Not every senior is on Telegram. And even Lakshmi — who uses WhatsApp daily — has days where she misses notifications, her phone is on silent, or she simply prefers a voice call. The Saath IVR system uses Exotel (Indian local numbers, TRAI-compliant) plus Twilio (US/global numbers for Priya) with Google Cloud TTS Neural2 voices, to call Lakshmi directly on her mobile. No app. No Telegram. Just a phone call in her language.

| When IVR triggers IVR is the escalation channel, not the default. It fires when: (a) a medication reminder goes unanswered for 45 minutes after the 2-snooze cap, (b) a URGENT-level anomaly flag needs immediate human acknowledgement, or (c) Priya manually triggers a wellness check from the dashboard. |
| :---- |

### **6.6.1 Flow A — Missed medication escalation (most common)**

Scenario: Lakshmi missed her 9:00 PM dinner reminder. She snoozed twice and the auto-Skip fired. The system has now gone 45 minutes with no acknowledgement. IVR escalation begins.

| \# | Agent action |
| :---- | :---- |
| 1 | SchedulerAgent → detects that Lakshmi's 9:00 PM Metformin \+ Atorvastatin \+ Glimepiride reminder has exhausted both snoozes and auto-Skipped at 9:34 PM. No "Took it" logged. Flags as missed\_critical (Metformin is a twice-daily drug critical for glycaemic control). Triggers IVR escalation job at 9:45 PM IST. |
| 2 | IVRAgent → generates a personalised TTS script for Lakshmi in Tamil (her native language). Script: "Lakshmi amma, naan Saath pesugiren. Innikku iravu unkal Metformin, Atorvastatin, mattum Glimepiride marandu vittirukkal. Ippothe eduthukolungal. Oru vilakku kettaal, 1 anukku. Enakku villai vittaal, 2 anukku." (Lakshmi amma, this is Saath. You missed your Metformin, Atorvastatin, and Glimepiride tonight. Please take them now. Press 1 to confirm. Press 2 to skip.) |
| 3 | Exotel → places outbound call to Lakshmi's mobile. Call connects in \~12 s. IVRAgent's TTS plays in Tamil at a slow, clear pace. Pauses after the question. |
| 4 | Lakshmi (phone) → hears her name and the word "Saath." Recognises context immediately. Reaches for her tablets. Presses 1\. |
| 5 | IVRAgent → DTMF tone 1 received. Plays confirmation: "Nandri, Lakshmi amma. Naan unkal Priya-kukku solluvean." (Thank you, Lakshmi amma. I will let Priya know.) Call ends. Total call duration: \~38 s. |
| 6 | Backend API → writes med\_reminder\_event: { drug: "Metformin 1000mg, Atorvastatin 20mg, Glimepiride 2mg", event: "taken\_via\_ivr", channel: "ivr\_call", timestamp: "21:46 IST" }. Updates compliance record. Marks IVR escalation as resolved. |
| 7 | CommsAgent → sends Priya a Telegram notification: "📞 Amma missed her dinner meds and wasn't responding on Telegram — Saath called her directly. She's confirmed she took them at 9:46 PM. All good. ✅" |
| 8 | ManagedAgent (next morning) → includes in brief: "Last night's dinner meds were taken after an IVR call at 9:46 PM — slight delay but full compliance achieved." Priya's brief reflects accurate compliance. |

### **6.6.2 Flow B — URGENT anomaly voice alert (parallel outbound)**

Scenario: a URGENT-level anomaly has been detected — new lab shows eGFR at 42, below the Metformin dose-review threshold of 45\. Telegram alone is not enough. Saath calls both Lakshmi and Priya in parallel within 90 seconds of detection.

| \# | Agent action |
| :---- | :---- |
| 1 | DDIAgent / LabAgent → flags anomaly as URGENT. Supervisor classifies: immediate action required. |
| 2 | IVRAgent → generates two scripts simultaneously: one for Lakshmi (Tamil), one for Priya (English-Indian accent). |
| 3 | Lakshmi script (Tamil TTS) → "Lakshmi amma, naan Saath. Ungal recent blood test-il oru mukkiyamana vishayam irukku. Ungal doctor-ai indhave azhaikka vendum. Ungal magal Priya-kidum sollirukkiream." (Lakshmi amma, this is Saath. There's something important in your recent blood test. You should call your doctor today. I've informed your daughter Priya.) |
| 4 | Priya script (English TTS) → "Hi, this is Saath calling about Lakshmi Iyer. Her latest lab results show her kidney function reading has dropped to 42 — below the threshold where her current Metformin dose needs physician review. We recommend calling her doctor today. Please check your Saath dashboard for full details." |
| 5 | Exotel \+ Twilio → places both calls in parallel. Lakshmi on Indian local number (Exotel). Priya on US number (Twilio). Both fire within 90 s of anomaly detection. |
| 6 | Lakshmi (phone) → hears the message. Presses 1 ("Understood"). IVRAgent logs acknowledgement. |
| 7 | Priya (phone) → answers. Hears the alert. Presses 1 ("Opening dashboard now"). Dashboard deep link sent via Telegram immediately after call ends. |
| 8 | Backend → logs both IVR acknowledgements. Sends Telegram follow-ups with dashboard link. Priya opens dashboard, sees the eGFR chart, calls Lakshmi's nephrologist within the hour. |

### **6.6.3 Flow C — Priya-triggered wellness check with symptom tree**

Scenario: it's Wednesday. Priya hasn't heard from her mother in two days and has a gut feeling. She opens the dashboard and taps "📞 Wellness Check Call."

| \# | Agent action |
| :---- | :---- |
| 1 | Priya (dashboard) → taps "📞 Wellness Check Call" on Lakshmi's profile card. Dashboard shows: "Saath will call Amma in her language and ask how she's feeling. You'll get a summary in 5 minutes." |
| 2 | WellnessIVRAgent → generates a warm, conversational script in Hindi (Lakshmi's functional language — warmer for casual check-ins than Tamil formal register). Script: "Namaste Lakshmi ji\! Main Saath bol raha hoon. Aap kaisi hain aaj? Koi takleef toh nahi? Agar theek hain toh 1 dabao, agar kuch problem hai toh 2 dabao, aur doctor se baat karni hai toh 3 dabao." |
| 3 | Exotel → places call to Lakshmi. She answers on the second ring. |
| 4 | Lakshmi (phone) → presses 2 — something is wrong. IVRAgent plays: "Kya hua ji? Agar sar dard hai toh 1 dabao. Agar pet mein dard hai toh 2 dabao. Agar chakkar aa raha hai toh 3 dabao. Kuch aur hai toh 4 dabao." |
| 5 | Lakshmi (phone) → presses 3 — dizziness. IVRAgent plays: "Samajh gaya. Priya ko abhi bata deta hoon. Aap baith jaiye aur pani piiye. Main unhe call karwa deta hoon." |
| 6 | WellnessIVRAgent → structures symptom report: { symptom: "dizziness", senior\_id: Lakshmi, timestamp: now, severity: "self-reported", context: "Amlodipine \+ Telmisartan both taken this morning — orthostatic hypotension is a known risk" }. Routes to DDIAgent for context enrichment. |
| 7 | DDIAgent → context: Amlodipine 5mg \+ Telmisartan 40mg both taken at 8:30 AM. Dizziness at 2:00 PM. Likely orthostatic hypotension — a known side effect of this combination, especially in elderly patients with CKD. Flag: MEDIUM. Recommendation: rise slowly, hydrate, call physician if persists \>1 hour. |
| 8 | CommsAgent → sends Priya an immediate Telegram alert: "📞 Amma pressed 'something's wrong' on her wellness check — she reported dizziness. Given her Amlodipine \+ Telmisartan combination, this may be blood pressure-related dizziness. Recommend calling her now and watching her BP today. \[Open Dashboard →\] \[Call Amma →\]" |
| 9 | Priya → calls Lakshmi immediately. Confirms she's sitting down and feeling a bit better. Asks her to check her BP with the home monitor. BP is 88/58 — low. Priya calls her physician. Telmisartan dose adjusted at the next visit. |

### **6.6.4 IVR system specification**

| Component | Spec / detail |
| :---- | :---- |
| Telephony — India | Exotel — Indian local numbers, TRAI-compliant, no international call tariffs for Lakshmi. KYC file on Day 1; 48 h approval. |
| Telephony — Global | Twilio — Priya's US number alerts and any other diaspora geography. |
| Backup (India) | Plivo India trunk via Pipecat (v3.0 spec) — fallback if Exotel KYC delays. |
| TTS engines | Google Cloud Text-to-Speech Neural2: hi-IN-Neural2-A (Hindi female) · ta-IN-Neural2-A (Tamil female) · en-IN-Neural2-D (English Indian for Priya). Sarvam Bulbul v3 as an upgraded Hindi voice option. |
| Input method | DTMF (keypad) — no speech recognition required in Phase 1; works on any phone including feature phones. |
| Trigger types | Missed medication escalation (45 min after snooze cap) · URGENT anomaly alert · Priya-triggered wellness check · Weekly adherence summary call (optional, configurable). |
| Max call duration | 90 s — intentionally short; Lakshmi should never feel talked at. |
| Retry logic | If no answer: retry after 10 min, then 20 min. After 3 failed attempts escalate to Priya via Telegram: "Couldn't reach Amma by phone — please call her directly." |
| Language selection | Set during onboarding by Priya; can be varied per call type (Tamil for medication, Hindi for wellness). |
| Compliance | All IVR calls preceded by a 1-second "This is Saath, your health companion" identifier. TRAI DND registry checked before any outbound call. Call logs stored and auditable. No dosage instructions voiced. |
| Phase 1 status | Functional feature in the demo — live outbound call shown during judging. |
| Phase 2 enhancement | Add speech recognition (Google STT) so Lakshmi can answer in natural language: "haan, le li" (yes, took it) → NLU maps to taken event. |

### **6.6.5 IVR scripts reference table**

| Trigger | Language | Script summary | DTMF options |
| :---- | :---- | :---- | :---- |
| Missed medication (dinner) | Tamil / Hindi | Identifies self, names missed medications, asks for confirmation | 1 \= Took it  ·  2 \= Skip tonight |
| URGENT anomaly (lab/DDI) | Tamil for Lakshmi; English for Priya | States urgency, names finding in plain language, instructs action | 1 \= Understood  ·  2 \= Call doctor now (connects to pre-set physician number) |
| Wellness check | Hindi (default for casual) | Warm greeting; asks how she's feeling; branches on response | 1 \= Fine  ·  2 \= Not well (→ symptom tree)  ·  3 \= Talk to doctor |
| Symptom tree (after 2\) | Hindi | Named symptoms one by one | 1 \= Headache  ·  2 \= Stomach pain  ·  3 \= Dizziness  ·  4 \= Other |
| Weekly adherence summary | Tamil / Hindi | "You took X of Y medications this week — great job\!" (\>85%) or "Let's do a bit better this week" (\<85%) | 1 \= Thank you (ends call) |
| No-answer escalation to Priya | English | "Saath tried to reach Lakshmi 3 times and couldn't get through. Please call her directly." | 1 \= Calling her now  ·  2 \= She's with me, all fine |

## **6.7 R7 — Doctor Visit Report: "What Amma forgot to tell you"**

Lakshmi sees her GP once a month, her nephrologist every 3 months, her endocrinologist every 6 months. At every appointment the doctor asks "How have you been feeling?" and Lakshmi says "Theek hoon, Doctor sahab." She is not lying. She simply doesn't remember that she was dizzy on the 4th, had three consecutive missed Metformin doses in Week 2, or that her resting HR climbed steadily for 5 days before returning to baseline. These are precisely the signals a physician needs — and precisely what a patient can never recall under the pressure of a clinic appointment.

| The Saath Doctor Visit Report A clinician-grade, chronological summary of everything that happened since the last visit — generated automatically by the ReportAgent, formatted for the physician's workflow, printable or shareable as a PDF. The patient hands it over at the start of the consultation. The doctor reads it in 90 seconds and knows more about the last 90 days than a 20-minute consultation could surface. |
| :---- |

### **6.7.1 What the report contains**

| Section | Content | Source |
| :---- | :---- | :---- |
| Patient header | Name, age, conditions, current medications (with doses), attending physicians, report period (e.g., "March 1 – April 22, 2026"), generated date | Onboarding profile \+ medication list |
| Medication adherence summary | Per-drug compliance rate for the period. E.g., Metformin: 87% (19/22 missed doses highlighted by date). Visual heatmap grid — each day one cell, green/red/amber. Snooze patterns shown. | med\_reminder\_event table |
| Symptom log | Every symptom Lakshmi reported via IVR wellness checks or Telegram free-text, chronologically. "April 4 — reported dizziness (2:15 PM). DDI context: consistent with orthostatic hypotension from Amlodipine \+ Telmisartan combination." | IVR wellness check responses \+ Telegram inbound Q\&A logs |
| Vitals trend (Phase 2\) | Heart rate baseline \+ deviations, step count weekly averages, sleep quality trend, SpO2 readings, skin temperature anomalies. Each plotted as a 90-day sparkline. | Samsung Health Data SDK / simulated fixture (Phase 1\) |
| Lab timeline | All panels from the period, tabulated side-by-side. eGFR, HbA1c, creatinine, TSH, lipid panel — each with reference range, current value, trend arrow (↑ ↓ →), and delta from last reading. | lab\_panel table (vision-parsed PDFs) |
| AI clinical flags | All anomalies flagged during the period — DDI risks, lab trend alerts, vitals anomalies, IVR escalations. Each with date, flag level (MEDIUM / HIGH / URGENT), and action taken. | DDIAgent \+ LabAgent \+ VitalsAgent output logs |
| Missed / skipped events | List of all missed medication events with dates, times, and whether IVR escalation was triggered. Gives the physician a true picture of real-world adherence, not the patient's best-case recollection. | med\_reminder\_event filtered to missed/skipped |
| Questions Lakshmi asked Saath | Every free-text question Lakshmi sent to the Telegram bot. "What is Telma for?" "I feel dizzy after my morning tablets." Reveals what the patient was worrying about but didn't articulate at the last appointment. | Telegram inbound message log |
| Physician notes section (blank) | A structured blank section for the doctor to fill in: diagnosis update, medication changes, next follow-up date, referrals. Designed so the doctor can write on the printed report and hand a copy back to Lakshmi. | Template — pre-formatted |
| Footer | "This report was generated by Saath, an AI health companion. It is an informational summary based on self-reported data and sensor readings. It does not constitute medical advice. Physician review required." | Compliance requirement |

### **6.7.2 12-step report generation flow**

Priya opens the dashboard 2 days before Lakshmi's monthly GP appointment and taps "Generate Doctor Report." Here is the complete agent flow:

| \# | Agent action |
| :---- | :---- |
| 1 | Priya (dashboard) → selects report type: "General Physician Visit" (vs Nephrologist / Endocrinologist / Cardiologist / Emergency — each has a different emphasis template). Selects period: last 30 days. Optionally adds a note: "She mentioned feeling breathless twice this month — please check." |
| 2 | ReportAgent (orchestrator) → receives request. Loads full context for the period: all med\_reminder\_events, all lab\_panels, all IVR call logs, all Telegram inbound messages, all daily\_summary rows, all agent flags. Total context: \~180,000 tokens for a 90-day period. Well within Opus 4.7's 1M window. |
| 3 | AdherenceSubAgent → queries med\_reminder\_event for the period. Computes per-drug adherence rates. Identifies patterns: missed doses cluster on Tuesdays and Wednesdays (Lakshmi visits her sister those days and disrupts her routine). Flags the Metformin miss-streak in Week 2 (3 consecutive evening doses missed — clinically significant for glycaemic control). |
| 4 | SymptomSubAgent → pulls all IVR wellness check responses and Telegram free-text. Clusters by symptom type: dizziness (3 occurrences, all post-morning medications), fatigue (2 occurrences, both on days with \<5,000 steps), breathlessness (2 occurrences — Priya's note corroborated). Maps symptoms to dates. |
| 5 | LabSubAgent → retrieves all lab panels from the period. Computes deltas: eGFR 58 → 55 (−3, declining faster than prior quarter average of −3.5/quarter). HbA1c 7.8 → 7.9 (+0.1, trend worsening). TSH 2.4 → 2.3 (stable). Generates trend narrative for each biomarker. |
| 6 | DDISubAgent → retrieves all DDI flags from the period. Metformin-renal flag remains active (eGFR 55, approaching 45 threshold). Amlodipine \+ Telmisartan orthostatic hypotension risk — now corroborated by 3 dizziness reports from SymptomSubAgent. Elevates this flag from MEDIUM to HIGH. |
| 7 | ReportAgent (synthesis) → uses Opus 4.7 extended thinking to synthesize all sub-agent outputs into a coherent, clinician-readable narrative. Applies physician-visit report format template: executive summary first (3 sentences the doctor reads in 10 seconds), then detailed sections. Tone: clinical, factual, no hedging — written for a physician, not a patient. |
| 8 | ReportAgent → extended-thinking output: "Key flags for this visit: (1) eGFR 55 — consider nephrology referral and Metformin dose review. (2) Three episodes of post-medication dizziness — likely orthostatic hypotension from Amlodipine \+ Telmisartan combination; consider timing adjustment or dose review. (3) HbA1c trending upward (7.6 → 7.8 → 7.9 over 3 quarters) — glycaemic control deteriorating despite adherence; consider medication review. (4) Medication adherence 87% — missed Metformin doses cluster Tuesday/Wednesday." |
| 9 | PDFRenderAgent → formats the report into a clean, printable 2–3 page PDF. Saath branding in the header. Patient name \+ report period prominent. Physician name field pre-filled if stored. Heatmap grid rendered as a visual table. Trend arrows rendered as colored text symbols. Blank "Physician Notes" section at the end. |
| 10 | Dashboard → PDF available for download instantly. Dashboard shows preview. One-tap "Share with Doctor" generates a secure, time-limited link (expires in 7 days) that Priya can WhatsApp to the physician directly, or Lakshmi can show on her phone at the clinic. |
| 11 | Physician (clinic) → Dr. Sharma receives the PDF link or printed copy. Reads the 3-sentence executive summary. Immediately orders a nephrology referral and asks about the dizziness episodes. The appointment that would have been "theek hoon" becomes a clinically productive 20 minutes that results in two medication adjustments and a specialist referral. |
| 12 | CommsAgent (post-visit) → Priya logs the appointment outcome on the dashboard: "GP visit complete — nephrology referral placed, Amlodipine reduced to 2.5 mg." ReportAgent archives the visit record. Next month's report will note the medication change and track whether dizziness episodes reduce. |

### **6.7.3 Specialist-tailored report variants**

Different specialists need different emphases. The ReportAgent applies a different lens based on which doctor Lakshmi is visiting.

| Specialist type | Report emphasis | Key sections prioritised | De-emphasised |
| :---- | :---- | :---- | :---- |
| General Physician (monthly) | Whole-patient overview — everything | All sections equally. Executive summary leads. | Nothing omitted |
| Nephrologist (quarterly) | Kidney function, fluid balance, CKD-relevant medications | eGFR trend (full history) · Creatinine \+ uric acid · Metformin flag · BP medications · Fluid intake self-reports · SpO2 trend (Phase 2\) | Thyroid section condensed to one line |
| Endocrinologist (6-monthly) | Glycaemic control, thyroid stability, metabolic panel | HbA1c trend (full history) · Fasting glucose · Metformin \+ Glimepiride adherence · Levothyroxine adherence (fasting compliance) · TSH trend · Weight/activity correlation | Cardiovascular section condensed |
| Cardiologist (as needed) | Cardiovascular risk, BP control, lipid management | Resting HR trend (Phase 2\) · BP medication adherence (Amlodipine, Telmisartan) · Lipid panel trend · Exercise/step count · Dizziness episodes with BP context · Atorvastatin adherence | Thyroid \+ glycaemic condensed |
| Emergency / walk-in | Acute summary — last 7 days only, one page max | Current medications (full list with doses) · Any anomaly flags from last 7 days · Last known vitals · Known allergies · Emergency contact (Priya \+ number) | All trend data removed — acute context only |

### **6.7.4 Sample executive summary (what the physician reads first)**

| SAATH PATIENT REPORT — Lakshmi Iyer, 71F General Physician Visit  ·  Period: March 24 – April 22, 2026  ·  Generated: April 22, 2026 EXECUTIVE SUMMARY (for physician): Three flags require attention this visit: (1) eGFR has declined from 58 to 55 over the past quarter — faster than the prior trend of −3.5/quarter — and a nephrology referral should be considered; Metformin dose review is warranted if eGFR continues this trajectory. (2) Lakshmi reported dizziness on three separate occasions post-morning medication — consistent with orthostatic hypotension from the Amlodipine \+ Telmisartan combination; timing adjustment or dose review may help. (3) HbA1c has risen from 7.6 to 7.9 over three consecutive quarters despite 87% medication adherence — glycaemic control is deteriorating and a medication review is recommended. Medication adherence this period: 87%  *(Metformin missed doses cluster Tuesday/Wednesday — possible routine disruption)* Symptoms reported by patient: Dizziness ×3 (post-AM meds) · Fatigue ×2 (low-activity days) · Breathlessness ×2 (April 11, April 18\) *Full report with lab timeline, adherence heatmap, and symptom log follows on pages 2–3.* |
| :---- |

### **6.7.5 Report delivery options**

| Delivery method | How | Best for |
| :---- | :---- | :---- |
| Download PDF (dashboard) | Priya downloads from NRI dashboard. Prints at home, gives to Lakshmi to carry. | Planned visits where Priya is coordinating in advance |
| Secure share link (WhatsApp) | Dashboard generates a 7-day expiring link. Priya sends to physician's WhatsApp (standard in Indian clinical practice). | When physician is reachable on WhatsApp — common in Indian tier-1 cities |
| Lakshmi shows phone at clinic | Saath app (Phase 2\) or Telegram bot sends Lakshmi a PDF link she can show on her phone at the clinic. | Walk-in or same-day appointments where Priya isn't coordinating |
| Email to physician (Phase 2\) | Physician email stored in Priya's profile. One-tap "Email to Dr. Sharma" from dashboard. | Physicians with digital practices |
| ABHA-linked upload (Phase 2\) | Report auto-uploaded to Lakshmi's ABHA health locker. Physician with ABHA access can pull it from their EMR. | Fully integrated digital health workflow — the end state |

## **6.8 R8 — Safety, disclaimer, and refusal layer**

* R8.1 Persistent on-app and on-report disclaimer: "Saath is an informational summary based on self-reported data and sensor readings. It is not a medical device, does not provide diagnosis or treatment, and is not a substitute for a Registered Medical Practitioner. Physician review required."

* R8.2 A safety-gatekeeper subagent (.claude/agents/safety-gatekeeper.md) wraps every outbound string. Enforces: no dosage advice voiced on IVR, no diagnosis, descriptive \+ suggestive never prescriptive, mandatory physician-review referral on clinical flags.

* R8.3 Emergency-detection fallback: chest pain, stroke-like symptoms, severe breathlessness, suicidal ideation, or acute injury break out of the normal flow and voice a scripted emergency response naming India emergency number 112 and paging Priya with a priority flag.

| Required narration pattern *"Your eGFR has declined from 58 to 55 this quarter. This is an informational summary — please discuss with your nephrologist whether a Metformin dose review is appropriate."* Forbidden language: "you have", "your diabetes", "abnormal", "your screening result", "take X mg of Y". |
| :---- |

# **7\. Technical architecture**

## **7.1 Stack decisions (locked)**

| Layer | Choice | Rationale |
| :---- | :---- | :---- |
| Orchestrator | Pipecat (pipecat-ai) | First-class Sarvam \+ Anthropic \+ Exotel-compatible telephony, Smart Turn V3. Open-source, runs on Hetzner. |
| Voice hot-path LLM | Claude Haiku 4.5 | \~200 ms TTFT; excellent Hinglish; handles turn-taking on medication chatter. |
| Deep-reasoning LLM | Claude Opus 4.7 | 1 M context · 2,576 px vision · xhigh extended thinking · memory\_20250818 · Managed Agents fan-out. Used for: lab vision, DDI reasoning, longitudinal synthesis, Doctor Visit Report generation. |
| STT | Sarvam Saaras v3 (codemix) · Google Cloud STT (Tamil) | Best-in-class Hinglish; Google covers Tamil with higher quality than Sarvam's current Tamil model. |
| TTS | Sarvam Bulbul v3 (Hindi simran / kavya) · Google Cloud Neural2 (hi-IN, ta-IN, en-IN) | Sarvam for warm Hindi; Google Neural2 for Tamil (ta-IN-Neural2-A) and English-Indian (en-IN-Neural2-D for Priya's calls). |
| Telephony — India | Exotel SIP trunk | TRAI-compliant, Indian local numbers, no international call tariffs for Lakshmi. File KYC Day 1\. |
| Telephony — Global | Twilio | Priya's US number alerts; diaspora geographies. |
| Telephony backup | Plivo India trunk via Pipecat | Fallback if Exotel KYC delays. |
| Async messaging | Telegram Bot (python-telegram-bot) | Zero Meta-template-approval friction; 20 MB voice notes, 50 MB file sends for lab PDFs. |
| NRI brief delivery | Telegram (demo) \+ WhatsApp via Gupshup/Wati (mocked for demo, production path shown) | WhatsApp approval 1–3 weeks; won't clear in 5 days. |
| Lab OCR | Opus 4.7 vision at 2,576 px \+ pdfplumber fallback | Handles Thyrocare two-column layout, Dr Lal custom ref-range highlighting. |
| Wearable | Android Health Connect \+ fixture (Phase 1\) · Galaxy Watch 4+ via Samsung Health Data SDK (Phase 2\) | Schema forward-compatible. |
| Database | Postgres with pgcrypto (Railway US-East Phase 1; AWS ap-south-1 Phase 2\) | Encrypted at rest; TLS in transit. |
| Dev environment | Claude Code with .claude/agents/ subagents | Judges are the Claude Code team; subagents are demoable artifacts. |

## **7.2 Dual-model routing**

8. Inbound audio arrives at Pipecat (Telegram voice note or Exotel SIP).

9. Sarvam Saaras v3 (codemix) / Google STT transcribes to text in \~150 ms.

10. Haiku 4.5 receives transcript \+ user's profile.md \+ last 14 daily\_summary entries \+ tool definitions. Decides whether to answer directly or invoke deep\_health\_analysis / generate\_doctor\_report / flag\_ddi.

11. If direct: Haiku generates reply, TTS synthesizes audio, reply ships back in 600–1,000 ms.

12. If tool-invoked: Haiku emits a filler phrase immediately via TTS; in parallel a background worker assembles multi-year context and calls Opus 4.7 with effort: "xhigh", thinking: {display: "summarized"}.

13. Opus returns; Haiku receives the synthesis, formats it to conversational register and user's language, ships via TTS. End-to-end 2.5–4.5 s, covered by filler.

## **7.3 Agent fan-out (Managed Agents, mirrors CrossBeam)**

Saath's backend orchestrates four specialist sub-agents in parallel on every brief and every Doctor Visit Report request, mirroring the CrossBeam architecture that won Opus 4.6 first place. A Supervisor synthesizes outputs.

| Sub-agent | Responsibility |
| :---- | :---- |
| AdherenceSubAgent | Per-drug compliance, pattern detection (Tue/Wed miss cluster), miss-streak flagging. |
| LabSubAgent | Longitudinal biomarker deltas, trend narratives, declining-rate comparisons against prior quarter. |
| DDISubAgent | Drug-drug / drug-renal reasoning via Opus xhigh extended thinking. Elevates flags on symptom corroboration. |
| SymptomSubAgent | IVR \+ Telegram free-text symptom clustering, date-mapping, severity tagging. |
| VitalsSubAgent (Phase 2\) | Galaxy Watch stream processing: HR baseline \+ deviations, sleep quality, SpO2. |
| ReportAgent (supervisor) | Synthesizes sub-agent outputs into Doctor Visit Report (§6.7.2) or daily brief (§6.5). Applies specialist-variant templates. |
| IVRAgent \+ WellnessIVRAgent \+ SchedulerAgent \+ CommsAgent | Voice-channel orchestrators (§6.6). |
| safety-gatekeeper | Final pass on every outbound user- or physician-facing string. |
| hindi-response-shortener / tamil-response-shortener | Trims Haiku's draft to ≤2 sentences / ≤40 words for TTS. |

## **7.4 Data model**

* Per-user filesystem layout under /memories/{user\_id}/: profile.md · labs/{YYYY-MM-DD}.json · visits/{YYYY-MM-DD}.md · daily\_summary/{YYYY-MM-DD}.md · transcripts/ivr/{call\_id}.md · transcripts/telegram/{YYYY-WW}.md · consent.json.

* Postgres tables (pgcrypto-encrypted): user, medication, med\_reminder\_event, lab\_panel, ivr\_call\_log, telegram\_inbound, agent\_flag, daily\_summary, doctor\_report.

* Forward-compat vitals schema accepts both Phase 1 fixture and Phase 2 Samsung Health Data SDK payloads with zero agent-contract changes.

## **7.5 Opus 4.7 feature use — on-screen captions for the demo video**

The "Opus 4.7 Use" criterion is 25% of scoring. These captions appear on-screen at the corresponding moment:

* "1 M context · 4 quarters of labs \+ 90 days of medication events \+ every IVR \+ Telegram message in one prompt (\~180K tokens)"

* "2,576 px vision · reads the mg/dL column on Thyrocare PDF with 1:1 pixel coords" (up 3.3× from Opus 4.6)

* "xhigh extended thinking · DDIAgent reasons Metformin \+ eGFR 55 step-by-step before flagging"

* "Memory tool (memory\_20250818) · Lakshmi's profile, medications, consent persisted across sessions"

* "MCP-Atlas 77.3% · parallel calls to lab-parser \+ adherence \+ DDI \+ symptom sub-agents" (Opus 4.7 SOTA)

* "Managed Agents · 4 sub-agents fan-out concurrently; Supervisor synthesizes in one Opus pass"

# **8\. UX & interaction design**

| User | Channel | When used | Notes |
| :---- | :---- | :---- | :---- |
| Lakshmi | Telegram bot (Tamil / Hindi) | Default: medication reminders, free-text questions | Primary async channel; emoji \+ large text, no nested menus. |
| Lakshmi | Inbound IVR call (Exotel) | Escalation: missed-med (§6.6.1), URGENT alert (§6.6.2), wellness check (§6.6.3) | DTMF-only. Phase 2 adds speech recognition. |
| Priya | NRI dashboard (web) | Daily brief, lab upload, wellness-check trigger, report generation | English-first, India date/locale conventions. |
| Priya | Telegram (demo) / WhatsApp (prod) | Daily brief \+ URGENT push \+ post-IVR summaries | Production path is WhatsApp via Gupshup/Wati; mocked in demo. |
| Priya | Inbound IVR call (Twilio US) | URGENT anomaly parallel alert (§6.6.2) | English-Indian accent (en-IN-Neural2-D); dashboard deep link follows. |
| Physician | PDF (printed, WhatsApp share link, ABHA in Phase 2\) | At the start of each appointment | 3-sentence exec summary is the hook (§6.7.4). |

## **8.1 Visual design**

* Clinical blue / white palette. Accent \#2E75B6. No cream-and-serif (Anthropic's own prompting guide flags this as off-register for healthcare).

* Hindi Devanagari and Tamil rendering uses system-native fonts; never subsetted.

* Doctor Visit Report PDF uses a neutral typographic system tuned for physician scan-reading: left-aligned exec summary, right-aligned trend arrows, colored text symbols for ↑ ↓ →, heatmap grid for adherence.

# **9\. Regulatory, safety & privacy**

## **9.1 Compliance posture**

| Topic | Stance |
| :---- | :---- |
| SaMD classification | Lab summarization \+ DDI warning fall under CDSCO October 2025 draft guidance (likely Class B/C once finalized in 2026). Phase 1 framing: "informational summary, physician review recommended" — visible on every clinical output. Phase 2 adds physician sign-off. |
| Telemedicine Practice Guidelines 2020 | No autonomous AI clinical advice. All content is descriptive ("eGFR has declined") \+ suggestive ("recommend physician consult"), never prescriptive ("change your dose to X"). |
| DPDPA 2023 | Lakshmi (senior) is the Data Principal. Priya (child) has explicit delegated access via consent screen. All access revocable. No default next-of-kin enrolment. |
| Cross-border transfer | DPDPA Rule 15 negative list: US not blacklisted as of Apr 2026\. Priya in San Jose can view → permitted. Documented in privacy policy. |
| HIPAA | Not applicable — no US-based PHI created by a US healthcare provider. Priya's viewing of India-hosted data is not a HIPAA flow. |
| Demo disclaimer | Splash screen: "Demo for Built with Opus 4.7 hackathon. Synthetic patient data. Not a medical device." |

## **9.2 Mandatory disclaimer**

| Always-on disclaimer "Saath is an informational summary based on self-reported data and sensor readings. It is not a medical device, does not provide diagnosis or treatment, and is not a substitute for a Registered Medical Practitioner. Physician review required." |
| :---- |

## **9.3 Language contract**

* Forbidden: "you have diabetes", "abnormal", "take X mg of Y", "your disease risk is N%", "this is a diagnosis."

* Allowed: "eGFR has declined," "may be worth discussing," "consider nephrology referral," "physician review recommended."

* The IVR scripts never voice a specific dosage change. The Doctor Visit Report names flags but places every medication decision in the physician's blank "Physician Notes" section.

# **10\. Success metrics**

## **10.1 Hackathon demo criteria**

| Demo moment | Success signal |
| :---- | :---- |
| eGFR trend caught across 4 quarters | Chart visible; 78 → 71 → 65 → 58 labelled; decline highlighted amber. |
| DDI flag with extended thinking trace | DDIAgent reasoning trace visible on dashboard; Metformin-renal flag rendered. |
| 4 sub-agents firing in parallel | Trace UI shows concurrent fan-out with timestamps. |
| Lab PDF parsed in \<8 seconds | Timer visible on screen; structured JSON result appears. |
| Live IVR call to Lakshmi | Outbound Exotel call connects during judging; DTMF press logged; compliance record updated. |
| Hindi/Tamil reminder → Lakshmi taps → state change visible in Priya's dashboard within 5 s | Live Telegram message on second phone; dashboard card flips from 6/7 to 7/7. |
| Doctor Visit Report PDF generated | 12-step flow visible in logs; PDF downloads; 3-sentence exec summary prominent on page 1\. |
| Brief delivered to Priya's real Telegram during demo | Not a screenshot — live message lands during judging session. |

## **10.2 Post-launch production targets (Year 1, post Phase 2\)**

| Metric | Target |
| :---- | :---- |
| DAU per family (Priya opens brief) | ≥60% |
| Senior reminder response rate | ≥75% |
| Medication adherence improvement vs baseline | \+15 percentage points |
| Brief NPS (Priya) | \>50 |
| Monthly churn | \<5% |
| Avg lab reports parsed / family / month | 1.2 |
| Doctor Visit Reports generated / family / month | ≥1.0 |
| Galaxy Watch wear time (Phase 2\) | \>12 h/day, 5+ days/week |
| Anomaly alerts → physician consult conversion | \>30% |
| YC S27 success criteria | 10+ design-partner families · 1 physician retainer · 1 documented clinical "save" · \>90 days retained payment data |

# **11\. Build plan — 5 days \+ 1 buffer**

| Day | Theme | Deliverables |
| :---- | :---- | :---- |
| Day 1 · Apr 21 | Foundation | uv init Pipecat; install pipecat-ai\[anthropic,sarvam,google,daily,silero,exotel,twilio\]. Telegram bot receives Hindi/Tamil messages → Saaras v3 STT → Haiku 4.5 → Bulbul v3 / Google Neural2 TTS → reply. FILE EXOTEL INDIA KYC TODAY (48 h approval). Seed Lakshmi \+ Priya \+ Meera personas with hand-curated multi-quarter history. |
| Day 2 · Apr 22 | Opus deep path \+ memory \+ DDI | deep\_health\_analysis, flag\_ddi tools. Opus 4.7 call with xhigh \+ summarized thinking. memory\_20250818 tool with SQLite \+ filesystem backing. Four-agent fan-out (Adherence, Lab, DDI, Symptom) with Supervisor synthesis. |
| Day 3 · Apr 23 | Lab OCR \+ IVR flows A/B/C | Opus 4.7 vision pipeline on real Thyrocare / Dr Lal sample PDFs at 300 DPI → structured JSON. Exotel number live \+ KYC cleared. Implement Flow A (missed-med) \+ Flow B (URGENT parallel outbound to Lakshmi \+ Priya) \+ Flow C (Priya-triggered wellness) with full DTMF trees and Tamil \+ Hindi \+ English TTS scripts. |
| Day 4 · Apr 24 | Doctor Visit Report \+ brief \+ safety | ReportAgent 12-step pipeline end-to-end. PDFRenderAgent produces 2–3 page PDF. Specialist-variant templates (GP \+ Nephro \+ Endo \+ Cardio \+ Emergency). Daily brief to Priya's real Telegram. Prompt caching for cost (Hume reports 80% reduction). safety-gatekeeper subagent hard rules locked. |
| Day 5 · Apr 25 | Demo polish \+ video | Record 4-minute demo: live Exotel call to Lakshmi (Tamil missed-med flow) → Telegram message → Priya receives live brief → Priya taps "Generate Doctor Report" → PDF appears → 3-sentence exec summary shown to camera. 15 seconds of Claude Code (subagents, /ultraplan, multi-file edit). Final slide: "Why Opus 4.7 specifically." Clinical blue/white throughout. |
| Day 6 · Apr 26 | Buffer \+ submit | GitHub repo public with CLAUDE.md, .claude/agents/, eval suite on 3 personas, README with architecture diagram. Pre-recorded Loom walkthrough uploaded as Plan B. Submit before deadline. |

## **11.1 Monday-morning action items**

14. File Exotel India KYC today. Critical path — 48 h approval.

15. Pin pipecat-ai with all adapters. Verify Sarvam Bulbul v3 and Google Neural2 ta-IN billing.

16. Generate Lakshmi's 4-quarter lab history (eGFR 78→71→65→58, HbA1c 7.2→7.4→7.6→7.8) as Thyrocare-formatted PDFs for the vision demo. Never use real patient data.

17. Write CLAUDE.md declaring the sub-agents and the safety contract.

18. Write the 4-minute demo video script before a single line of voice code.

19. Write one disclaimer-compliant system prompt that defaults every clinical output toward "physician review recommended."

# **12\. Scope cuts & mocks (protect the ship date)**

## **12.1 Mocked for demo (production path shown)**

* WhatsApp Business API — demo uses Telegram; production path mocked with screenshot.

* ABDM / ABHA consent \+ report upload — pre-link one test ABHA ID; full OAuth is Phase 2\.

* Live Galaxy Watch — Phase 1 uses deterministic fixture matching the Samsung Health Data SDK payload schema.

* Speech-recognition IVR (NLU "haan, le li") — DTMF-only in Phase 1; speech in Phase 2\.

## **12.2 Cut entirely**

* Cancer risk scoring (CDSCO Class C landmine since Nov 2025).

* Bhojpuri as first-class language (beta: Hindi voice \+ AI4Bharat fallback).

* Autonomous dose recommendations — ReportAgent flags, never prescribes.

* Clinician-facing sign-off (Phase 3).

# **13\. Risks & mitigations**

| \# | Risk | Severity × likelihood | Mitigation |
| :---- | :---- | :---- | :---- |
| R1 | Opus 4.7 vision misreads synthetic Thyrocare PDF layout | High × Med | Test on 4 templates Day 1; pdfplumber fallback if vision confidence \<0.85. |
| R2 | Telegram bot rate-limited during demo | Med × Low | Polling mode \+ dedicated bot; pre-warm with test messages 30 min before demo. |
| R3 | Brief \+ report cost exceeds $0.50/run | Med × Med | Aggressive prompt caching of patient profile; cap context at 800K tokens; monitor per-run cost from Day 1\. |
| R4 | Live demo network failure or live IVR call doesn't connect | High × Low | Pre-record full Loom walkthrough Day 4 evening as Plan B — uploaded and ready. |
| R5 | Judges question "where's the watch?" | Med × High | Lead Phase 2 roadmap with Galaxy Watch already scoped; forward-compatible schemas shown. |
| R6 | Compliance question about clinical advice | Med × Med | Splash disclaimer; brief \+ report copy explicitly suggestive not prescriptive; physician-review framing throughout. |
| R7 | Synthetic data feels fake → loses credibility | Med × Med | Use real Thyrocare layout, real medication names, real Bengaluru pincode, real Stripe persona for Priya. |
| R8 | Phase 2 roadmap perceived as too far away | Low × Med | Phase 2 section names SDKs, effort estimates, forward-compatible schemas — signals execution readiness. |
| R9 | Exotel KYC delays | High × Med | File Monday; Plivo India trunk as backup; worst case demo IVR via Twilio India (higher cost, still works). |
| R10 | Hippocratic AI Front Door launched Apr 16, 2026 — judges conflate Saath with it | Med × High | One-line rebuttal in pitch: "hospital-to-patient front door vs patient-to-family continuous companion." |

# **14\. Demo narrative — 4-minute YouTube video**

| Time | Shot | Content |
| :---- | :---- | :---- |
| 0:00–0:25 | Naman to camera | "My parents are in Delhi. I live in Bangalore. My mom sent me a lab report last month I couldn't interpret. My dad didn't want to bother me about his knee pain. I learned about his BP climbing three weeks after the fact. This is the product I wish I had for them — and for 32 million NRI families just like mine." |
| 0:25–1:10 | Live Exotel IVR call (Flow A — missed med) | Lakshmi in Bengaluru missed her dinner meds; auto-Skip fires. Phone rings. Tamil TTS: "Lakshmi amma, naan Saath pesugiren…" She presses 1\. Call logs update live on dashboard. Telegram notification lands on Priya's phone on the second screen: "📞 Amma missed her dinner meds — Saath called her, she confirmed at 9:46 PM. All good. ✅" |
| 1:10–2:00 | Longitudinal reasoning on labs (the Opus 4.7 moment) | Priya drags 4 quarterly Thyrocare PDFs onto the dashboard. Opus 4.7 vision parses in \<8 s. Chart renders: eGFR 78 → 71 → 65 → 58\. DDIAgent trace appears: Metformin \+ eGFR 55 → approaching 45 dose-review threshold. Extended-thinking trace visible. On-screen caption: "Opus 4.7 · 1M context · xhigh extended thinking · 2,576 px vision · managed agents fan-out." |
| 2:00–2:50 | Doctor Visit Report generation (12-step flow) | Priya taps "Generate Doctor Report — GP visit." 12-step ReportAgent flow runs on screen (labels for each sub-agent). PDF renders. Cut to the 3-sentence executive summary: "Three flags require attention this visit: (1) eGFR has declined from 58 to 55… (2) three episodes of post-medication dizziness… (3) HbA1c trending upward." Specialist variant toggle — switch to Nephrologist view; Thyroid section collapses. |
| 2:50–3:30 | URGENT Flow B (if time) \+ brief to Priya | Simulated URGENT lab arrives (eGFR 42). Parallel outbound calls fire on two screens — Tamil to Lakshmi, English to Priya. Both press 1\. Priya's Telegram lands with dashboard deep link. Daily brief also shown: one paragraph, 5 data sources, one next action. |
| 3:30–3:50 | Technical depth | Architecture diagram. /memories/lakshmi/profile.md in editor. Five .claude/agents/\*.md files. 2-second Claude Code /ultraplan clip. Caption: "Built with Claude Code in 5 days · 9 sub-agents · 1 MCP server · 2,576 px vision · 1M context · memory tool · Managed Agents." |
| 3:50–4:00 | Vision close | "If we help 1% of India's 50 million aging parents live better — and help 1% of their children worry less — that's a million families. We built this in a week with Opus 4.7. We're going to ship it." |

# **15\. Roadmap**

| Phase | Headline | Deliverables | Timeline |
| :---- | :---- | :---- | :---- |
| 1 | Agent Brain — Hackathon | 4-agent parallel fan-out · 1M context longitudinal reasoning · Opus 4.7 vision PDF parsing · DDI extended thinking · IVR flows A/B/C · Doctor Visit Report with 5 specialist variants · ManagedAgent daily brief · Telegram Hindi/Tamil reminders · NRI dashboard | Apr 21–26, 2026 |
| 2 | Senses — Wearable \+ Real Channels | Galaxy Watch 4+ live vitals · Samsung Health Data SDK · Android companion app · Wear OS watch-face reminders · WhatsApp Business API via Gupshup · ABHA linkage for report upload · 1–2 physician retainers · AWS ap-south-1 migration · DPDPA full compliance posture · IVR speech recognition | 4–8 weeks post-hackathon |
| 3 | Hands — Clinical Loop | Physician-side dashboard · Retainer-panel sign-off workflow on reports · Fall-detection hardware partnership · Insurance B2B2C pilots · SaMD Class B/C compliance filing | 6–9 months |
| 4 | Scale — Multi-country \+ Voice | UK NHS-adjacent · Canada provincial · Voice-first interface for visually impaired seniors · AI-native chronic disease management (diabetes, CKD) | 12–18 months |
| **YC S27 target** By late 2026, Saath will demonstrate 10+ design-partner families with full Galaxy Watch integration live, one physician on retainer, paying customers at $30/month with \>90 days retained payment data, and one documented clinical "save." |  |  |  |

# **16\. Open questions**

* Pricing — is $30/month defensible from day one, or do we run an NRI freemium tier (first daily brief free, Doctor Visit Report paywalled) to overcome install friction?

* Should the ReportAgent ever auto-generate a report on a schedule (e.g., 2 days before every recurring appointment) rather than waiting for Priya's tap?

* Do we need a clinician advisory board for Series A credibility, or does product-led growth through NRI referrals carry us to a physician retainer pilot first?

* Exotel vs Plivo vs Twilio India — which is the single production telephony bet once we are past KYC?

* For Phase 2 WhatsApp, do we front-load the Gupshup integration or continue on Telegram until a physician retainer is signed?