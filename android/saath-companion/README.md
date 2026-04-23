# Saath Android Companion App

WorkManager-based daily sync from **Health Connect** → Saath backend.

Health Connect is the Android system-level health data broker. Samsung Health
writes Galaxy Watch metrics into it automatically once the user enables
sharing, so this app reads from a single standard API instead of a Samsung-
specific SDK. No Samsung Developer Portal, no AAR licence, no partner
approval.

## Requirements

- Android 10+ (API 29)
- Health Connect — pre-installed on Android 14+; installable from Play Store
  on Android 13 (the app prompts you if missing)
- Samsung Health app with the watch paired (or any Health Connect source —
  Google Fit, Fitbit, etc.)

## Getting the APK

### Option A — build in CI (recommended)

Every push to `main`, `day3/*`, `fix/*`, or `feature/*` branches that touches
`android/` triggers [.github/workflows/android-apk.yml](../../.github/workflows/android-apk.yml).
The debug APK lands as a workflow artifact named `saath-companion-debug-apk`.

You can also trigger it manually from the Actions tab → Android APK → Run
workflow.

### Option B — build locally

```bash
cd android/saath-companion
./gradlew :app:assembleDebug
```

The APK lands at `app/build/outputs/apk/debug/app-debug.apk`.

If `./gradlew` is missing (the wrapper is not committed), generate it:
```bash
gradle wrapper --gradle-version 8.11.1 --distribution-type bin
```

## Install + pair (on phone)

1. `adb install saath-companion-<sha>.apk` (or sideload via file manager).
2. Open Samsung Health → Settings → Health Connect → **enable sharing** for
   steps, heart rate, sleep, SpO₂, skin temperature, HRV, and exercise.
3. Open Saath → enter **Senior ID** (UUID of the senior in the backend's
   `app_user` table), **Shared Secret** (matching `WEARABLE_HMAC_SECRET`
   on the backend), and **Backend URL**.
4. Tap **Grant Permissions** → Health Connect shows the standard permission
   screen → tap Allow.
5. Tap **Finish**. A daily WorkManager job now POSTs a signed summary to
   `POST /wearable/samsung/webhook`.

## Testing end-to-end without a watch

The app falls back to a **mock reader** that posts a scripted
`dizziness_episode` payload (triggers HIGH/URGENT anomaly detection on the
backend → Telegram alert). This lets you verify the full pipeline with just
the APK, before pairing a real watch.

The mock reader is used automatically when Health Connect permissions are not
granted. To force it once permissions are granted, adb-set
`saath_prefs.use_mock_reader` to `true` in the app's shared preferences, or
uninstall + reinstall and skip permission grant during onboarding.

## Architecture

```
Galaxy Watch → Samsung Health app → Health Connect (Android system)
                                         ↓
                         androidx.health.connect.client
                                         ↓
                         HealthConnectReader  ──┐
                                                ├─→ SyncWorker
                         MockWearableReader  ──┘      ↓
                                                   HMAC-signed
                                                   HTTP POST
                                                      ↓
                                         /wearable/samsung/webhook
                                                      ↓
                                          wearable_daily_summary
                                          + VitalsAnomalyAgent
                                          + Telegram alert
```

Files:

| File | Role |
|---|---|
| `data/WearableReader.kt` | Vendor-neutral interface + `MockWearableReader` fixture |
| `data/HealthConnectReader.kt` | Real reader — one `readRecords` per metric |
| `data/HealthConnectAvailability.kt` | SDK status check + Play Store installer intent |
| `data/HmacSigner.kt` | HMAC-SHA256 + Base64 matching backend Pydantic |
| `data/WebhookClient.kt` | OkHttp POST with `X-Saath-Signature` header |
| `data/SyncWorker.kt` | CoroutineWorker — 24h periodic; retries on 5xx, fails on 4xx |
| `domain/Permissions.kt` | The set of Health Connect read permissions |
| `AndroidManifest.xml` | Declared permissions + rationale intent filter |

## Health Connect limitations

Two Samsung-proprietary scores are not exposed via Health Connect and will be
sent as `null`:

- `stress_score` — no native Health Connect record
- `sleep_score` — Samsung-proprietary composite; derivable from
  `SleepStagesRecord` if you need it

Both are nullable on the backend — the anomaly detector doesn't rely on them.

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| "Health Connect is not available" | Android 13 without the provider app | Tap Install / Update Health Connect (opens Play Store) |
| Permission screen auto-dismisses | Missing rationale intent filter | Already wired in `AndroidManifest.xml` — confirm the activity-alias is present |
| 401 from backend | Wrong shared secret | Verify `WEARABLE_HMAC_SECRET` matches backend `.env` |
| Sync works but records are empty | Samsung Health hasn't synced to Health Connect | Open Samsung Health → Settings → Health Connect → enable sharing |
| Worker never fires | Battery optimization | Exempt Saath from battery optimization in Android Settings |
