package com.saath.companion.data

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import java.time.LocalDate

/**
 * Periodic WorkManager job that POSTs a 7-day rolling window of wearable
 * summaries to the Saath backend — the current day and the six prior days.
 *
 * Why 7 days on every run:
 *   - First install needs a backfill so guardians see context, not just
 *     "today only".
 *   - Older days can still change — Samsung Health writes sleep stages
 *     and post-workout HR corrections hours after the activity ended.
 *   - The backend's webhook is idempotent (ON CONFLICT (senior_id, date)
 *     DO UPDATE), so re-POSTing old dates is a harmless upsert.
 *
 * Configuration comes in via `inputData`:
 *   - seniorId:  UUID of the senior in the backend's `app_user` table
 *   - secret:    shared HMAC secret (must match WEARABLE_HMAC_SECRET on backend)
 *   - backendUrl: base URL of the Saath API (e.g. https://saath.example.com)
 *   - useMockReader: when true, reads fixture data (dizziness_episode
 *                    varied per day) instead of calling Health Connect.
 *
 * Failure semantics: per-day reads and posts are independent. A failure on
 * one day does not abort the rest. The worker returns:
 *   - Result.success() if at least one day POST succeeded
 *   - Result.retry()   if no successes and at least one transient failure
 *   - Result.failure() if no successes and all failures were 4xx (config bug)
 *
 * The worker never crashes the process.
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
            Log.e(
                TAG,
                "sync_aborted missing_config senior=${seniorId.isNotBlank()} " +
                    "secret=${secret.isNotBlank()} url=${backendUrl.isNotBlank()}",
            )
            return Result.failure()
        }

        val reader: WearableReader = if (useMock) {
            MockWearableReader()
        } else {
            HealthConnectReader(applicationContext)
        }
        val client = WebhookClient(baseUrl = backendUrl, secret = secret)

        val today = LocalDate.now()
        // Today first, then walk backwards. Today gets priority — if the
        // worker is killed mid-run (battery, etc.) the user still sees their
        // freshest data on the backend.
        val dates: List<LocalDate> = (0 until WINDOW_DAYS).map { today.minusDays(it.toLong()) }

        var okCount = 0
        var transientFailCount = 0
        var permanentFailCount = 0

        for (date in dates) {
            val summary: WearableDailySummary = try {
                reader.readDailySummary(seniorId, date)
            } catch (exc: Throwable) {
                Log.w(TAG, "read_failed date=$date: ${exc.message}", exc)
                transientFailCount++
                continue
            }

            val result = try {
                client.postDailySummary(summary)
            } catch (exc: Throwable) {
                Log.w(TAG, "post_failed date=$date: ${exc.message}", exc)
                transientFailCount++
                continue
            }

            when {
                result.ok -> {
                    Log.i(TAG, "sync_ok date=$date status=${result.status}")
                    okCount++
                }
                result.status in 400..499 -> {
                    Log.e(
                        TAG,
                        "sync_4xx date=$date status=${result.status} " +
                            "body=${result.body.take(200)}",
                    )
                    permanentFailCount++
                }
                else -> {
                    Log.w(TAG, "sync_5xx date=$date status=${result.status}")
                    transientFailCount++
                }
            }
        }

        Log.i(
            TAG,
            "sync_summary window=$WINDOW_DAYS ok=$okCount " +
                "transient=$transientFailCount permanent=$permanentFailCount",
        )

        return when {
            okCount > 0 -> Result.success()
            transientFailCount > 0 -> Result.retry()
            else -> Result.failure()
        }
    }

    companion object {
        const val KEY_SENIOR_ID = "senior_id"
        const val KEY_SECRET = "secret"
        const val KEY_BACKEND_URL = "backend_url"
        const val KEY_USE_MOCK_READER = "use_mock_reader"

        /** How many days of history each sync covers: today + (WINDOW_DAYS-1) prior. */
        const val WINDOW_DAYS = 7

        private const val TAG = "SyncWorker"
    }
}
