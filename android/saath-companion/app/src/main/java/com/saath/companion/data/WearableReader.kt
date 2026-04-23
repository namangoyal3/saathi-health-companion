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
 * Fixture reader for demos and tests. Generates realistic-looking values
 * that vary per date (deterministic, hash-based) so a 7-day backfill
 * doesn't produce seven identical rows.
 *
 * The *current date* is calibrated to the backend's "dizziness_episode"
 * scenario — HIGH/URGENT anomalies fire end-to-end (Telegram alert path
 * exercised). Prior days are calmer so the anomaly trend line has shape.
 */
class MockWearableReader : WearableReader {

    override suspend fun readDailySummary(
        seniorId: String,
        date: LocalDate,
    ): WearableDailySummary {
        val today = LocalDate.now()
        val daysAgo = java.time.temporal.ChronoUnit.DAYS.between(date, today).toInt()

        return if (daysAgo <= 0) {
            // Today — dizziness_episode payload: triggers HIGH/URGENT detection
            WearableDailySummary(
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
        } else {
            // Prior days — calmer, deterministically varied by date hash
            val jitter = (date.toEpochDay().toInt() * 31) and 0x7fffffff
            WearableDailySummary(
                seniorId = seniorId,
                date = date.toString(),
                steps = 5000 + (jitter % 5000),
                avgHeartRate = 65 + (jitter % 20),
                sleepMinutes = 360 + (jitter % 120),
                sleepEfficiencyPct = 78 + (jitter % 15),
                sleepScore = 70 + (jitter % 20),
                avgSpo2Pct = 95 + (jitter % 5),
                avgSkinTempC = 36.4 + ((jitter % 10).toDouble() / 10.0),
                hrvRmssd = 35 + (jitter % 20),
                stressScore = 30 + (jitter % 30),
                exerciseMinutes = 15 + (jitter % 45),
            )
        }
    }
}
