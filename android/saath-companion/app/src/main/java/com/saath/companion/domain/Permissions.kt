package com.saath.companion.domain

import android.util.Log
import com.samsung.android.sdk.health.data.DataTypes
import com.samsung.android.sdk.health.data.permission.AccessType
import com.samsung.android.sdk.health.data.permission.Permission

object SamsungHealthPermissions {
    val ALL = setOf<Permission>(
        Permission.of(DataTypes.STEPS, AccessType.READ),
        Permission.of(DataTypes.HEART_RATE, AccessType.READ),
        Permission.of(DataTypes.SLEEP, AccessType.READ),
        Permission.of(DataTypes.BLOOD_OXYGEN, AccessType.READ),
        Permission.of(DataTypes.SKIN_TEMPERATURE, AccessType.READ),
        Permission.of(DataTypes.EXERCISE, AccessType.READ),
        Permission.of(DataTypes.STRESS, AccessType.READ),
    )

    fun log() {
        Log.i("SaathPermissions", "Requesting ${ALL.size} Samsung Health permissions")
    }
}
