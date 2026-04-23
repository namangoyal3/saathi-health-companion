package com.saath.companion

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import androidx.work.*
import com.saath.companion.data.SyncWorker
import com.saath.companion.domain.SamsungHealthPermissions
import com.saath.companion.ui.onboarding.PairScreen
import com.saath.companion.ui.onboarding.PermissionScreen
import com.saath.companion.ui.onboarding.WelcomeScreen
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

private const val PREFS = "saath_prefs"
private const val KEY_SENIOR_ID = "senior_id"
private const val KEY_SECRET = "secret"
private const val KEY_STEP = "onboarding_step"
private const val KEY_LAST_SYNC = "last_sync_epoch"

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        setContent {
            var step by remember { mutableIntStateOf(prefs.getInt(KEY_STEP, 0)) }
            var seniorId by remember { mutableStateOf(prefs.getString(KEY_SENIOR_ID, "") ?: "") }
            var secret by remember { mutableStateOf(prefs.getString(KEY_SECRET, "") ?: "") }
            val lastSyncEpoch = prefs.getLong(KEY_LAST_SYNC, 0L)
            val lastSyncedText = if (lastSyncEpoch == 0L) {
                "Never synced"
            } else {
                val dt = Instant.ofEpochMilli(lastSyncEpoch)
                    .atZone(ZoneId.systemDefault())
                    .format(DateTimeFormatter.ofPattern("d MMM, HH:mm"))
                "Last synced: $dt"
            }

            when (step) {
                0 -> WelcomeScreen(onNext = {
                    step = 1
                    prefs.edit().putInt(KEY_STEP, 1).apply()
                })

                1 -> PairScreen(
                    seniorId = seniorId,
                    secret = secret,
                    onSeniorIdChange = { seniorId = it },
                    onSecretChange = { secret = it },
                    onNext = {
                        prefs.edit()
                            .putString(KEY_SENIOR_ID, seniorId)
                            .putString(KEY_SECRET, secret)
                            .putInt(KEY_STEP, 2)
                            .apply()
                        step = 2
                    },
                )

                2 -> PermissionScreen(
                    lastSyncedText = lastSyncedText,
                    onRequestPermissions = { requestSamsungHealthPermissions() },
                    onDone = { scheduleDailySync() },
                )
            }
        }
    }

    private fun requestSamsungHealthPermissions() {
        // Samsung Health SDK permission request — requires HealthDataStore connection.
        // Full wiring requires the AAR; placeholder logs intent.
        SamsungHealthPermissions.log()
    }

    private fun scheduleDailySync() {
        val req = PeriodicWorkRequestBuilder<SyncWorker>(24, TimeUnit.HOURS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()
        WorkManager.getInstance(this)
            .enqueueUniquePeriodicWork(
                "saath_daily_sync",
                ExistingPeriodicWorkPolicy.KEEP,
                req,
            )
    }
}
