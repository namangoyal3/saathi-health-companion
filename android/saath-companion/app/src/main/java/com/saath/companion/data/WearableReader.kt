package com.saath.companion.data

import java.time.LocalDate

/**
 * Reads one day of aggregated wearable metrics for a senior.
 *
 * Two implementations:
 *  - [MockWearableReader]: deterministic fixture, used when running the app
 *    without a real wearable (demos, first-launch before permissions granted,
 *    CI smoke tests).
 *  - [HealthConnectReader]: reads from Android's Health Connect, which
 *    Samsung Health (and Google Fit, Fitbit, etc.) writes into.
 *
 * The interface is vendor-neutral so a second reader (e.g. Apple
 * HealthKit bridge in the future) can drop in without touching SyncWorker.
 *
 * Fields may be null when the wearable did not record that signal. Steps
 * default to 0 because zero is a meaningful value, not missing data.
 */
interface WearableReader {
    suspend fun readDailySummary(seniorId: String, date: LocalDate): WearableDailySummary
}

/**
 * Fixture reader matching the backend's "dizziness_episode" scenario from
 * app/api/vitals_simulator.py — fires a HIGH/URGENT anomaly detection so
 * the end-to-end flow (including Telegram alert) can be verified with one
 * install-and-run.
 */
class MockWearableReader : WearableReader {
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
