package com.saath.companion.data

import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class WebhookClient(
    private val baseUrl: String,
    private val secret: String,
    private val json: Json = Json { encodeDefaults = false; explicitNulls = false },
    private val http: OkHttpClient = defaultHttp(),
) {

    data class PostResult(val ok: Boolean, val status: Int, val body: String)

    fun postDailySummary(summary: WearableDailySummary): PostResult {
        val bodyString = json.encodeToString(WearableDailySummary.serializer(), summary)
        val bodyBytes = bodyString.toByteArray(Charsets.UTF_8)
        val signature = HmacSigner.sign(secret, bodyBytes)

        val req = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/wearable/samsung/webhook")
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Saath-Signature", signature)
            .post(bodyBytes.toRequestBody(JSON_MEDIA))
            .build()

        http.newCall(req).execute().use { resp ->
            val respBody = resp.body?.string().orEmpty()
            return PostResult(resp.isSuccessful, resp.code, respBody)
        }
    }

    companion object {
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()

        private fun defaultHttp(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }
}
