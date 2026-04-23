package com.saath.companion

import android.content.Context
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.ActivityResultLauncher
import androidx.compose.runtime.*
import androidx.health.connect.client.PermissionController
import androidx.work.*
import com.saath.companion.data.HealthConnectAvailability
import com.saath.companion.data.HealthConnectAvailabilityChecker
import com.saath.companion.data.SyncWorker
import com.saath.companion.domain.SaathHealthPermissions
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
private const val KEY_BACKEND_URL = "backend_url"
private const val KEY_USE_MOCK_READER = "use_mock_reader"
private const val KEY_STEP = "onboarding_step"
private const val KEY_LAST_SYNC = "last_sync_epoch"
private const val KEY_PERMISSIONS_GRANTED = "hc_permissions_granted"

class MainActivity : ComponentActivity() {

    private lateinit var requestPermissions:
        ActivityResultLauncher<Set<String>>

    private val grantedState = mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        grantedState.value = prefs.getBoolean(KEY_PERMISSIONS_GRANTED, false)

        // Health Connect permission launcher — must be registered BEFORE
        // onStart() per ActivityResult API contract.
        requestPermissions = registerForActivityResult(
            PermissionController.createRequestPermissionResultContract()
        ) { granted: Set<String> ->
            val allGranted = granted.containsAll(SaathHealthPermissions.READ_PERMISSIONS)
            grantedState.value = allGranted
            prefs.edit().putBoolean(KEY_PERMISSIONS_GRANTED, allGranted).apply()
            Log.i(
                "SaathMain",
                "hc_permissions granted=${granted.size}/${SaathHealthPermissions.READ_PERMISSIONS.size} all=$allGranted",
            )
        }

        setContent {
            var step by remember { mutableIntStateOf(prefs.getInt(KEY_STEP, 0)) }
            var seniorId by remember { mutableStateOf(prefs.getString(KEY_SENIOR_ID, "") ?: "") }
            var secret by remember { mutableStateOf(prefs.getString(KEY_SECRET, "") ?: "") }
            var backendUrl by remember { mutableStateOf(prefs.getString(KEY_BACKEND_URL, "") ?: "") }
            val granted = grantedState.value
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
                    backendUrl = backendUrl,
                    onSeniorIdChange = { seniorId = it },
                    onSecretChange = { secret = it },
                    onBackendUrlChange = { backendUrl = it },
                    onNext = {
                        prefs.edit()
                            .putString(KEY_SENIOR_ID, seniorId)
                            .putString(KEY_SECRET, secret)
                            .putString(KEY_BACKEND_URL, backendUrl)
                            .putInt(KEY_STEP, 2)
                            .apply()
                        step = 2
                    },
                )

                2 -> PermissionScreen(
                    lastSyncedText = lastSyncedText,
                    permissionsGranted = granted,
                    healthConnectStatus = HealthConnectAvailabilityChecker.check(this),
                    onInstallHealthConnect = {
                        HealthConnectAvailabilityChecker.launchProviderInstaller(this)
                    },
                    onRequestPermissions = {
                        requestPermissions.launch(SaathHealthPermissions.READ_PERMISSIONS)
                    },
                    onSyncNow = {
                        // Trigger an immediate sync without leaving the screen.
                        // Same reader-selection logic as Finish — use real
                        // HealthConnectReader if perms granted, mock otherwise.
                        val useMock = !grantedState.value
                        prefs.edit().putBoolean(KEY_USE_MOCK_READER, useMock).apply()
                        enqueueImmediateSync(prefs)
                    },
                    onDone = {
                        val useMock = !grantedState.value
                        prefs.edit().putBoolean(KEY_USE_MOCK_READER, useMock).apply()
                        scheduleDailySync(prefs)
                    },
                )
            }
        }
    }

    private fun buildInputData(prefs: android.content.SharedPreferences): Data =
        Data.Builder()
            .putString(SyncWorker.KEY_SENIOR_ID, prefs.getString(KEY_SENIOR_ID, "") ?: "")
            .putString(SyncWorker.KEY_SECRET, prefs.getString(KEY_SECRET, "") ?: "")
            .putString(SyncWorker.KEY_BACKEND_URL, prefs.getString(KEY_BACKEND_URL, "") ?: "")
            .putBoolean(SyncWorker.KEY_USE_MOCK_READER, prefs.getBoolean(KEY_USE_MOCK_READER, true))
            .build()

    private fun networkConstraint(): Constraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    private fun enqueueImmediateSync(prefs: android.content.SharedPreferences) {
        val req = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(networkConstraint())
            .setInputData(buildInputData(prefs))
            .build()
        WorkManager.getInstance(this)
            .enqueueUniqueWork("saath_initial_sync", ExistingWorkPolicy.REPLACE, req)
    }

    private fun scheduleDailySync(prefs: android.content.SharedPreferences) {
        val wm = WorkManager.getInstance(this)

        // Periodic: every 15 minutes (Android's PeriodicWorkRequest minimum).
        // Each run backfills today + last 6 days, so older rows stay correct
        // while today refreshes near-live. PeriodicWorkRequest does NOT fire
        // immediately on enqueue — the first run lands at the end of the
        // first period. That's why the immediate one-time below exists.
        val periodic = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(networkConstraint())
            .setInputData(buildInputData(prefs))
            .build()
        wm.enqueueUniquePeriodicWork(
            "saath_daily_sync",
            ExistingPeriodicWorkPolicy.UPDATE,
            periodic,
        )
        enqueueImmediateSync(prefs)
    }
}
