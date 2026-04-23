package com.saath.companion.data

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.HeartRateVariabilityRmssdRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.SkinTemperatureRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/**
 * Reads a day of aggregated wearable metrics from Android's Health Connect.
 *
 * Samsung Health (and Google Fit / Fitbit / etc.) write raw records into
 * Health Connect automatically once the user grants sharing in the Samsung
 * Health app — so this single implementation covers any combination of
 * wearables the user owns.
 *
 * Per-metric reads are independent: a failure on one metric (e.g. the user
 * hasn't granted SkinTemperature) returns null for that field but still
 * produces a summary. Steps defaults to 0 when no records exist.
 *
 * Two Samsung-proprietary metrics are not exposed by Health Connect and
 * are always null in this reader:
 *   - stress_score: no native HC record
 *   - sleep_score:  Samsung-proprietary composite
 * Both are nullable on the backend — omitting them is safe.
 */
class HealthConnectReader(context: Context) : WearableReader {

    private val client: HealthConnectClient = HealthConnectClient.getOrCreate(context)
    private val zone: ZoneId = ZoneId.systemDefault()

    override suspend fun readDailySummary(
        seniorId: String,
        date: LocalDate,
    ): WearableDailySummary = withContext(Dispatchers.IO) {
        val start: Instant = date.atStartOfDay(zone).toInstant()
        val end: Instant = date.plusDays(1).atStartOfDay(zone).toInstant()
        val window = TimeRangeFilter.between(start, end)

        WearableDailySummary(
            seniorId = seniorId,
            date = date.toString(),
            steps = safeInt("steps") { readSteps(window) } ?: 0,
            avgHeartRate = safeInt("avg_hr") { readAvgHeartRate(window) },
            sleepMinutes = safeInt("sleep_min") { readSleepMinutes(window, start, end) },
            sleepEfficiencyPct = null,          // derivable from SleepStagesRecord; skip for now
            sleepScore = null,                  // Samsung-proprietary, not in HC
            avgSpo2Pct = safeInt("spo2") { readAvgSpo2Pct(window) },
            avgSkinTempC = safeDouble("skin_temp") { readAvgSkinTempC(window) },
            hrvRmssd = safeInt("hrv") { readAvgHrvRmssd(window) },
            stressScore = null,                 // not in HC
            exerciseMinutes = safeInt("exercise_min") { readExerciseMinutes(window) },
        )
    }

    private suspend fun readSteps(window: TimeRangeFilter): Int {
        val resp = client.readRecords(
            ReadRecordsRequest(StepsRecord::class, window)
        )
        return resp.records.sumOf { it.count }.toInt()
    }

    private suspend fun readAvgHeartRate(window: TimeRangeFilter): Int? {
        val resp = client.readRecords(
            ReadRecordsRequest(HeartRateRecord::class, window)
        )
        val samples = resp.records.flatMap { it.samples }
        if (samples.isEmpty()) return null
        return (samples.sumOf { it.beatsPerMinute } / samples.size.toDouble()).toInt()
    }

    private suspend fun readSleepMinutes(
        window: TimeRangeFilter,
        start: Instant,
        end: Instant,
    ): Int? {
        val resp = client.readRecords(
            ReadRecordsRequest(SleepSessionRecord::class, window)
        )
        if (resp.records.isEmpty()) return null
        val totalMillis = resp.records.sumOf { s ->
            val overlapStart = maxOf(s.startTime, start)
            val overlapEnd = minOf(s.endTime, end)
            Duration.between(overlapStart, overlapEnd).toMillis().coerceAtLeast(0L)
        }
        return (totalMillis / 60_000L).toInt()
    }

    private suspend fun readAvgSpo2Pct(window: TimeRangeFilter): Int? {
        val resp = client.readRecords(
            ReadRecordsRequest(OxygenSaturationRecord::class, window)
        )
        if (resp.records.isEmpty()) return null
        val mean = resp.records.sumOf { it.percentage.value } / resp.records.size
        return mean.toInt()
    }

    private suspend fun readAvgSkinTempC(window: TimeRangeFilter): Double? {
        val resp = client.readRecords(
            ReadRecordsRequest(SkinTemperatureRecord::class, window)
        )
        val baselines = resp.records.mapNotNull { it.baseline?.inCelsius }
        if (baselines.isEmpty()) return null
        return baselines.average()
    }

    private suspend fun readAvgHrvRmssd(window: TimeRangeFilter): Int? {
        val resp = client.readRecords(
            ReadRecordsRequest(HeartRateVariabilityRmssdRecord::class, window)
        )
        if (resp.records.isEmpty()) return null
        val mean = resp.records.sumOf { it.heartRateVariabilityMillis } / resp.records.size
        return mean.toInt()
    }

    private suspend fun readExerciseMinutes(window: TimeRangeFilter): Int? {
        val resp = client.readRecords(
            ReadRecordsRequest(ExerciseSessionRecord::class, window)
        )
        if (resp.records.isEmpty()) return null
        val totalMillis = resp.records.sumOf { s ->
            Duration.between(s.startTime, s.endTime).toMillis().coerceAtLeast(0L)
        }
        return (totalMillis / 60_000L).toInt()
    }

    private inline fun safeInt(tag: String, block: () -> Int?): Int? = try {
        block()
    } catch (exc: Throwable) {
        Log.w(TAG, "read_failed metric=$tag: ${exc.message}")
        null
    }

    private inline fun safeDouble(tag: String, block: () -> Double?): Double? = try {
        block()
    } catch (exc: Throwable) {
        Log.w(TAG, "read_failed metric=$tag: ${exc.message}")
        null
    }

    private companion object {
        const val TAG = "HealthConnectReader"
    }
}
