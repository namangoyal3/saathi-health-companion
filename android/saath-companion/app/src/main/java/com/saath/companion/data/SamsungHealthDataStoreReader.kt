package com.saath.companion.data

import android.content.Context
import android.util.Log
import com.samsung.android.sdk.health.data.DataTypes
import com.samsung.android.sdk.health.data.HealthDataService
import com.samsung.android.sdk.health.data.HealthDataStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/**
 * Real Samsung Health reader. Requires the Samsung Health Data SDK AAR at
 * `app/libs/samsung-health-data-api-1.0.0.aar` — see
 * android/saath-companion/README.md for download + Developer-Mode setup.
 *
 * This class is intentionally structural: each metric is extracted in its own
 * `try { } catch` so a single permission gap or empty day doesn't fail the
 * whole sync. The field-level decoding (mapping SDK result rows into our
 * aggregate Int/Double fields) is marked TODO — the Samsung SDK's exact
 * aggregated-record shape depends on the installed SDK version, and must be
 * verified against the device response on first run.
 *
 * When a metric cannot be read it is left null; the webhook treats null as
 * "not recorded today" rather than zero.
 */
class SamsungHealthDataStoreReader(context: Context) : SamsungHealthReader {

    private val store: HealthDataStore = HealthDataService.getStore(context)
    private val zone: ZoneId = ZoneId.systemDefault()

    override suspend fun readDailySummary(
        seniorId: String,
        date: LocalDate,
    ): WearableDailySummary = withContext(Dispatchers.IO) {
        val startInstant: Instant = date.atStartOfDay(zone).toInstant()
        val endInstant: Instant = date.plusDays(1).atStartOfDay(zone).toInstant()

        WearableDailySummary(
            seniorId = seniorId,
            date = date.toString(),
            steps = readIntSafe("steps") { readSteps(startInstant, endInstant) } ?: 0,
            avgHeartRate = readIntSafe("avg_hr") { readAvgHeartRate(startInstant, endInstant) },
            sleepMinutes = readIntSafe("sleep_min") { readSleepMinutes(startInstant, endInstant) },
            sleepEfficiencyPct = readIntSafe("sleep_eff") { readSleepEfficiencyPct(startInstant, endInstant) },
            sleepScore = readIntSafe("sleep_score") { readSleepScore(startInstant, endInstant) },
            avgSpo2Pct = readIntSafe("spo2") { readAvgSpo2(startInstant, endInstant) },
            avgSkinTempC = readDoubleSafe("skin_temp") { readAvgSkinTempC(startInstant, endInstant) },
            hrvRmssd = readIntSafe("hrv") { readHrvRmssd(startInstant, endInstant) },
            stressScore = readIntSafe("stress") { readStressScore(startInstant, endInstant) },
            exerciseMinutes = readIntSafe("exercise_min") { readExerciseMinutes(startInstant, endInstant) },
        )
    }

    private inline fun readIntSafe(tag: String, block: () -> Int?): Int? = try {
        block()
    } catch (exc: Throwable) {
        Log.w(TAG, "read_failed metric=$tag: ${exc.message}")
        null
    }

    private inline fun readDoubleSafe(tag: String, block: () -> Double?): Double? = try {
        block()
    } catch (exc: Throwable) {
        Log.w(TAG, "read_failed metric=$tag: ${exc.message}")
        null
    }

    // -------------------------------------------------------------------------
    // Per-metric readers.
    //
    // Each reader targets a concrete DataType and aggregates across the
    // 24-hour window [start, end). The Samsung SDK's response shape is
    // version-dependent, so field decoding is left TODO — log and return null
    // until a first-run device trace confirms the exact aggregate keys.
    // -------------------------------------------------------------------------

    @Suppress("UNUSED_PARAMETER")
    private fun readSteps(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): store.aggregateData(AggregateRequest.Builder(DataTypes.STEPS)...)
        //   → sum the step count across the window, return total or null.
        logUnimplemented(DataTypes.STEPS)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readAvgHeartRate(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): aggregate mean(beatsPerMinute) over the window
        logUnimplemented(DataTypes.HEART_RATE)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readSleepMinutes(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): sum sleep-session duration across the window
        logUnimplemented(DataTypes.SLEEP)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readSleepEfficiencyPct(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): sleep_efficiency field on the SleepSession summary
        logUnimplemented(DataTypes.SLEEP)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readSleepScore(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): sleep_score field if exposed by SleepSession.score
        logUnimplemented(DataTypes.SLEEP)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readAvgSpo2(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): aggregate mean(spo2_pct) over BLOOD_OXYGEN samples
        logUnimplemented(DataTypes.BLOOD_OXYGEN)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readAvgSkinTempC(start: Instant, end: Instant): Double? {
        // TODO(samsung-sdk): aggregate mean(skin_temp_c) over SKIN_TEMPERATURE samples
        logUnimplemented(DataTypes.SKIN_TEMPERATURE)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readHrvRmssd(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): HRV is often exposed as a derived field on
        //   HEART_RATE aggregates or a dedicated HRV type depending on SDK
        //   version. Verify against the device trace on first run.
        logUnimplemented(DataTypes.HEART_RATE)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readStressScore(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): mean(stress_score) over STRESS samples
        logUnimplemented(DataTypes.STRESS)
        return null
    }

    @Suppress("UNUSED_PARAMETER")
    private fun readExerciseMinutes(start: Instant, end: Instant): Int? {
        // TODO(samsung-sdk): sum(duration_minutes) across EXERCISE sessions
        logUnimplemented(DataTypes.EXERCISE)
        return null
    }

    private fun logUnimplemented(dataType: Any) {
        Log.w(TAG, "samsung_reader_unimplemented type=$dataType store=$store")
    }

    private companion object {
        const val TAG = "SamsungHealthReader"
    }
}
