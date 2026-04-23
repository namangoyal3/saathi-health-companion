package com.saath.companion.domain

import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.HeartRateVariabilityRmssdRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.SkinTemperatureRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord

/**
 * Health Connect permission set. Samsung Health syncs these records into
 * Health Connect on the device, so reading from Health Connect gives us
 * Galaxy Watch data without any Samsung SDK, AAR, or Developer Portal
 * registration.
 *
 * Two Samsung-proprietary metrics are intentionally absent:
 *   - stress_score: no native Health Connect record
 *   - sleep_score:  Samsung-proprietary; derive from SleepSessionRecord
 *                   stages if needed, or leave null.
 * Both fields are nullable on the backend — omitting them is fine.
 */
object SaathHealthPermissions {

    val READ_PERMISSIONS: Set<String> = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(OxygenSaturationRecord::class),
        HealthPermission.getReadPermission(SkinTemperatureRecord::class),
        HealthPermission.getReadPermission(HeartRateVariabilityRmssdRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
    )
}
