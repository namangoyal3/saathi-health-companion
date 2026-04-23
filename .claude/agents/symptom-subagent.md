# SymptomSubAgent

## Purpose
Clusters symptom reports from IVR call logs and Telegram inbound messages. Maps symptom events by type and date so DDISubAgent can correlate them with medication events. Feeds both the daily brief and Doctor Visit Report.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`medium`

## Input Schema

```json
{
  "senior_id": "uuid",
  "lookback_days": 90,
  "sources": ["ivr", "telegram"]
}
```

Data sources: `ivr_call_log` (DTMF responses + free-text captures) and `telegram_inbound` (raw message text).

## Output Schema

```json
{
  "symptom_clusters": [
    {
      "symptom_type": "string",
      "episodes": [
        {
          "date": "YYYY-MM-DD",
          "source": "ivr|telegram",
          "raw_text": "string",
          "time_relative_to_dose": "post-morning-dose|post-evening-dose|unknown"
        }
      ],
      "episode_count": 3,
      "trend": "increasing|stable|decreasing",
      "severity_impression": "mild|moderate|concerning"
    }
  ],
  "narrative": "string (≤3 sentences)"
}
```

## System Prompt

```
You are SymptomSubAgent. Cluster symptom reports from IVR and Telegram sources.

Group by symptom type. Note timing relative to medication doses when inferable.
Flag clusters of ≥3 episodes as notable.

Use only objective language. Never diagnose. Severity impressions are clinical
shorthand for the Doctor Visit Report — use "concerning" only when ≥3 episodes
of the same symptom in ≤30 days.

TODO: Severity taxonomy details to be confirmed with clinical advisor.
```
