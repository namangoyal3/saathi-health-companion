package com.saath.companion.data

import java.time.LocalDate

/**
 * Reads one day of aggregated health metrics.
 *
 * Two impls:
 *  - [MockSamsungHealthReader]: deterministic fixture for unit tests and for
 *    running the app end-to-end without the Samsung SDK AAR in place.
 *  - [SamsungHealthDataStoreReader]: real HealthDataStore calls. Compiles only
 *    once `samsung-health-data-api-1.0.0.aar` is dropped into `app/libs/`.
 *
 * Keeping the SDK behind this interface means the rest of the app — SyncWorker,
 * webhook client, serialization — compiles and runs against the mock, and we
 * can swap the real reader in without touching the worker.
 */
interface SamsungHealthReader {

    /**
     * Fetch aggregated metrics for [date] in the device's local timezone.
     *
     * Fields may be null when the wearable did not record that signal
     * (e.g. no sleep tracked the prior night, HRV not measured). Steps
     * default to 0 because zero is a meaningful value, not missing data.
     */
    suspend fun readDailySummary(seniorId: String, date: LocalDate): WearableDailySummary
}

/**
 * Fixture reader used for (a) instrumentation/unit tests and (b) running the
 * app against a live backend without the Samsung SDK AAR in place.
 *
 * The values roughly track the "dizziness_episode" scenario from
 * backend/app/api/vitals_simulator.py so anomaly detection fires end-to-end.
 */
class MockSamsungHealthReader : SamsungHealthReader {
    override suspend fun readDailySummary(
        seniorId: String,
        date: LocalDate,
    ): WearableDailySummary = WearableDailySummary(
        seniorId = seniorId,
        date = date.toString(),
        steps = 1600,
        avgHeartRate = 112,
        sleepMinutes = 270,
        sleepEfficiencyPct = 64,
        sleepScore = 48,
        avgSpo2Pct = 88,
        avgSkinTempC = 37.1,
        hrvRmssd = 18,
        stressScore = 78,
        exerciseMinutes = 5,
    )
}
