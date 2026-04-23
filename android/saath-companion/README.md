# Saath Android Companion App

WorkManager-based daily sync from Samsung Health to the Saath backend.

## Requirements

- Android 10+ (API 29) with Samsung Health 6.x installed
- Samsung Galaxy device (Watch data sync requires Galaxy Watch + Health app)
- Galaxy Store: Samsung Health Data SDK must be approved for the app's package name

## Samsung Health SDK Setup

The Samsung Health Data SDK AAR is **not redistributed** in this repo (Samsung
Developer agreement). Download it manually:

1. Go to <https://developer.samsung.com/health/android/data/guide/overview.html>
2. Download `samsung-health-data-api-<version>.aar`
3. Rename it to `samsung-health-data-api-1.0.0.aar`
4. Place it at `app/libs/samsung-health-data-api-1.0.0.aar`

`build.gradle.kts` picks it up via `fileTree(dir = "libs", include = ["*.aar"])`.

## Samsung Health Developer Mode (required for testing on non-certified apps)

Samsung Health enforces package-name allowlisting in production. To test during
development:

1. Open **Samsung Health** on your Galaxy device.
2. Tap the **three-dot menu** (top right) → **Settings**.
3. Scroll to **About Samsung Health** and tap the version number **10 times**
   rapidly. You will see "Developer mode is now ON."
4. Go back to Settings → **Developer** → toggle **Data permissions** to allow
   your app's package (`com.saath.companion`).

Without this, all `HealthDataStore` calls throw `SecurityException`.

## Building

```bash
# From android/saath-companion/
./gradlew assembleDebug
```

Place the AAR in `app/libs/` first or the build will fail with an unresolved
dependency error.

## Configuration

At first launch the app asks for:
- **Senior ID** — UUID of the senior in the Saath Postgres `app_user` table
- **Shared Secret** — `WEARABLE_HMAC_SECRET` from the backend `.env`
- **Backend URL** — base URL of the Saath API (e.g. `https://saath.example.com`)

These are stored in private `SharedPreferences`. WorkManager re-reads them on
every run via `inputData`.

## How sync works

`SyncWorker` runs once every 24 hours when the device is online:

1. Reads the previous day's data from Samsung Health (Steps, HR, Sleep, SpO₂,
   Skin Temp, HRV, Stress, Exercise) via `HealthDataStore`.
2. Serialises to `WearableDailySummary` JSON.
3. Signs the body with HMAC-SHA256 (shared secret) → `X-Saath-Signature` header.
4. POSTs to `POST /wearable/samsung/webhook`.

The backend upserts into `wearable_daily_summary` and logs the event.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `SecurityException: Permission denied` | Developer Mode not enabled or package not allowlisted | See Developer Mode steps above |
| `ClassNotFoundException: HealthDataService` | AAR missing from `app/libs/` | Download and place AAR |
| `401 Unauthorized` from backend | Wrong shared secret | Re-check `WEARABLE_HMAC_SECRET` in `.env` |
| Worker never fires | No network constraint met | Connect to WiFi or disable constraint in `MainActivity` for testing |
