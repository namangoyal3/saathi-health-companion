package com.saath.companion.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Verifies that WearableDailySummary serializes to the exact JSON shape the
 * backend expects. Mirrors the three Kotlin-style round-trip scenarios the
 * backend's Python test harness already validated (full / sparse / minimal).
 */
class ModelsSerializationTest {

    private val json = Json { encodeDefaults = false; explicitNulls = false }

    @Test
    fun serialize_allFields_matchesDeclarationOrder() {
        val s = WearableDailySummary(
            seniorId = "00000000-0000-0000-0000-000000000001",
            date = "2026-04-23",
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
        val out = json.encodeToString(WearableDailySummary.serializer(), s)

        // Spot-check all 12 keys are present
        listOf(
            "senior_id", "date", "steps", "avg_heart_rate", "sleep_minutes",
            "sleep_efficiency_pct", "sleep_score", "avg_spo2_pct",
            "avg_skin_temp_c", "hrv_rmssd", "stress_score", "exercise_minutes",
        ).forEach { key ->
            assertTrue("missing key: $key in $out", out.contains("\"$key\""))
        }

        // Declaration order — senior_id before date before steps
        val idxSenior = out.indexOf("senior_id")
        val idxDate = out.indexOf("\"date\"")
        val idxSteps = out.indexOf("\"steps\"")
        assertTrue("order broken", idxSenior < idxDate && idxDate < idxSteps)
    }

    @Test
    fun serialize_nullsOmitted_wireStaysCompact() {
        val s = WearableDailySummary(
            seniorId = "00000000-0000-0000-0000-000000000001",
            date = "2026-04-23",
            steps = 6500,
            avgHeartRate = 72,
            avgSpo2Pct = 98,
            // every other field null — must NOT appear in wire format
        )
        val out = json.encodeToString(WearableDailySummary.serializer(), s)

        // Present
        assertTrue(out.contains("\"avg_heart_rate\":72"))
        assertTrue(out.contains("\"avg_spo2_pct\":98"))
        // Omitted
        assertFalse("sleep_minutes should be omitted when null: $out", out.contains("sleep_minutes"))
        assertFalse("sleep_score should be omitted when null: $out", out.contains("sleep_score"))
        assertFalse("hrv_rmssd should be omitted when null: $out", out.contains("hrv_rmssd"))
        assertFalse("stress_score should be omitted when null: $out", out.contains("stress_score"))
    }

    @Test
    fun serialize_minimalPayload_parseableByBackend() {
        // Equivalent to the "kotlin-style minimal" scenario validated against
        // FastAPI TestClient — only senior_id + date + steps required.
        val s = WearableDailySummary(
            seniorId = "00000000-0000-0000-0000-000000000001",
            date = "2026-04-23",
            steps = 0,
        )
        val out = json.encodeToString(WearableDailySummary.serializer(), s)
        assertEquals(
            """{"senior_id":"00000000-0000-0000-0000-000000000001","date":"2026-04-23","steps":0}""",
            out,
        )
    }

    @Test
    fun hmac_overSerializedBody_matchesPythonReference() {
        // End-to-end: build the JSON like the SyncWorker does, sign it with
        // HmacSigner, verify the signature matches what Python computed for
        // the same body + secret. Proves the full Kotlin → backend contract.
        val s = WearableDailySummary(
            seniorId = "00000000-0000-0000-0000-000000000001",
            date = "2026-04-23",
            steps = 1600,
        )
        val body = json.encodeToString(WearableDailySummary.serializer(), s).toByteArray(Charsets.UTF_8)
        val sig = HmacSigner.sign("real-secret-abc", body)
        // Python-computed reference for this exact body + secret
        assertEquals("wq9jOPsNynxhETxOuwIe1r6hcJQIITKVmhCRk0C1jiQ=", sig)
    }
}
