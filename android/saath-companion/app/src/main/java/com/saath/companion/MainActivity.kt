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
                    onDone = {
                        // Default to mock reader until HC permissions are granted
                        // — means the app produces a signed POST on first run
                        // even without a watch paired, so the backend pipeline
                        // can be verified end-to-end.
                        val useMock = !grantedState.value
                        prefs.edit().putBoolean(KEY_USE_MOCK_READER, useMock).apply()
                        scheduleDailySync(prefs)
                    },
                )
            }
        }
    }

    private fun scheduleDailySync(prefs: android.content.SharedPreferences) {
        val inputData = Data.Builder()
            .putString(SyncWorker.KEY_SENIOR_ID, prefs.getString(KEY_SENIOR_ID, "") ?: "")
            .putString(SyncWorker.KEY_SECRET, prefs.getString(KEY_SECRET, "") ?: "")
            .putString(SyncWorker.KEY_BACKEND_URL, prefs.getString(KEY_BACKEND_URL, "") ?: "")
            .putBoolean(SyncWorker.KEY_USE_MOCK_READER, prefs.getBoolean(KEY_USE_MOCK_READER, true))
            .build()

        val req = PeriodicWorkRequestBuilder<SyncWorker>(24, TimeUnit.HOURS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .setInputData(inputData)
            .build()
        WorkManager.getInstance(this)
            .enqueueUniquePeriodicWork(
                "saath_daily_sync",
                ExistingPeriodicWorkPolicy.UPDATE,
                req,
            )
    }
}
