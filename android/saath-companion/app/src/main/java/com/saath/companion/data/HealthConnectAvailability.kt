package com.saath.companion.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.health.connect.client.HealthConnectClient

/**
 * Health Connect availability checker + installer-intent helper.
 *
 * Status interpretation:
 *  - AVAILABLE: Health Connect is on the device and ready to use.
 *  - PROVIDER_UPDATE_REQUIRED: Health Connect is installed but needs an update
 *    — launch the Play Store via [launchProviderInstaller].
 *  - NOT_AVAILABLE: Device OS too old or Health Connect was uninstalled.
 *    Android 14+ has it built-in; Android 13 needs the Play Store install.
 */
enum class HealthConnectAvailability { AVAILABLE, PROVIDER_UPDATE_REQUIRED, NOT_AVAILABLE }

object HealthConnectAvailabilityChecker {

    fun check(context: Context): HealthConnectAvailability =
        when (HealthConnectClient.getSdkStatus(context, HEALTH_CONNECT_PROVIDER)) {
            HealthConnectClient.SDK_AVAILABLE -> HealthConnectAvailability.AVAILABLE
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED ->
                HealthConnectAvailability.PROVIDER_UPDATE_REQUIRED
            else -> HealthConnectAvailability.NOT_AVAILABLE
        }

    /**
     * Open Play Store on the Health Connect provider so the user can
     * install / update it. Falls back to the Play Store web URL on devices
     * without a Play Store app.
     */
    fun launchProviderInstaller(context: Context) {
        val playStoreIntent = Intent(Intent.ACTION_VIEW).apply {
            setPackage("com.android.vending")
            data = Uri.parse(
                "market://details?id=$HEALTH_CONNECT_PROVIDER&url=healthconnect%3A%2F%2Fonboarding"
            )
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        try {
            context.startActivity(playStoreIntent)
        } catch (_: Throwable) {
            val web = Intent(
                Intent.ACTION_VIEW,
                Uri.parse("https://play.google.com/store/apps/details?id=$HEALTH_CONNECT_PROVIDER"),
            ).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK }
            context.startActivity(web)
        }
    }

    private const val HEALTH_CONNECT_PROVIDER = "com.google.android.apps.healthdata"
}
