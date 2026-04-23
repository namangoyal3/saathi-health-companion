package com.saath.companion.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Mirrors `WearableDailySummary` in backend/app/api/wearable.py.
 *
 * Field names + order must match — the HMAC is computed over the JSON body,
 * so any reordering or renaming on either side breaks signature verification.
 * The backend uses `json.dumps(body).encode()` (Python default separators),
 * so we serialize with kotlinx.serialization's default formatting and omit
 * nulls to keep both bodies byte-identical for shared test fixtures.
 */
@Serializable
data class WearableDailySummary(
    @SerialName("senior_id") val seniorId: String,
    @SerialName("date") val date: String,
    @SerialName("steps") val steps: Int,
    @SerialName("avg_heart_rate") val avgHeartRate: Int? = null,
    @SerialName("sleep_minutes") val sleepMinutes: Int? = null,
    @SerialName("sleep_efficiency_pct") val sleepEfficiencyPct: Int? = null,
    @SerialName("sleep_score") val sleepScore: Int? = null,
    @SerialName("avg_spo2_pct") val avgSpo2Pct: Int? = null,
    @SerialName("avg_skin_temp_c") val avgSkinTempC: Double? = null,
    @SerialName("hrv_rmssd") val hrvRmssd: Int? = null,
    @SerialName("stress_score") val stressScore: Int? = null,
    @SerialName("exercise_minutes") val exerciseMinutes: Int? = null,
)
