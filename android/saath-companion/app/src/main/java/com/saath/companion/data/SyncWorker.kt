package com.saath.companion.data

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import java.time.LocalDate

/**
 * Periodic WorkManager job that reads the previous day's summary from Samsung
 * Health and POSTs it (HMAC-signed) to the Saath backend.
 *
 * Configuration comes in via `inputData`:
 *   - seniorId:  UUID of the senior in the backend's `app_user` table
 *   - secret:    shared HMAC secret (must match WEARABLE_HMAC_SECRET on backend)
 *   - backendUrl: base URL of the Saath API (e.g. https://saath.example.com)
 *   - useMockReader: when true (default until AAR is present), reads fixture
 *                    data instead of calling HealthDataStore. Lets the end-to-end
 *                    flow be verified against a real backend without the SDK.
 *
 * Failure semantics: transient network/5xx errors retry. 4xx auth failures
 * (invalid secret, bad payload shape) return Result.failure — there's no
 * point retrying bad input. The worker never crashes the process.
 */
class SyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val seniorId = inputData.getString(KEY_SENIOR_ID).orEmpty()
        val secret = inputData.getString(KEY_SECRET).orEmpty()
        val backendUrl = inputData.getString(KEY_BACKEND_URL).orEmpty()
        val useMock = inputData.getBoolean(KEY_USE_MOCK_READER, true)

        if (seniorId.isBlank() || secret.isBlank() || backendUrl.isBlank()) {
            Log.e(TAG, "sync_aborted missing_config senior=${seniorId.isNotBlank()} secret=${secret.isNotBlank()} url=${backendUrl.isNotBlank()}")
            return Result.failure()
        }

        val reader: WearableReader = if (useMock) {
            MockWearableReader()
        } else {
            HealthConnectReader(applicationContext)
        }

        // Read today's running total so the user sees live step counts during
        // demos. For production daily summaries flip back to .minusDays(1).
        val target = LocalDate.now()

        val summary: WearableDailySummary = try {
            reader.readDailySummary(seniorId, target)
        } catch (exc: Throwable) {
            Log.w(TAG, "read_failed — will retry next cycle: ${exc.message}", exc)
            return Result.retry()
        }

        val client = WebhookClient(baseUrl = backendUrl, secret = secret)
        val result = try {
            client.postDailySummary(summary)
        } catch (exc: Throwable) {
            Log.w(TAG, "post_failed — will retry next cycle: ${exc.message}", exc)
            return Result.retry()
        }

        return when {
            result.ok -> {
                Log.i(TAG, "sync_ok status=${result.status} date=${summary.date}")
                Result.success()
            }
            result.status in 400..499 -> {
                Log.e(TAG, "sync_4xx status=${result.status} body=${result.body.take(200)} — not retrying")
                Result.failure()
            }
            else -> {
                Log.w(TAG, "sync_5xx status=${result.status} — retrying")
                Result.retry()
            }
        }
    }

    companion object {
        const val KEY_SENIOR_ID = "senior_id"
        const val KEY_SECRET = "secret"
        const val KEY_BACKEND_URL = "backend_url"
        const val KEY_USE_MOCK_READER = "use_mock_reader"
        private const val TAG = "SyncWorker"
    }
}
