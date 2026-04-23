package com.saath.companion.data

import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Full WebhookClient round-trip against a mock backend. Simulates exactly what
 * the real Saath FastAPI webhook receives, so any silent drift in HMAC
 * signing, JSON shape, or header names fails the test.
 */
class WebhookClientTest {

    private lateinit var server: MockWebServer
    private val sampleSummary = WearableDailySummary(
        seniorId = "00000000-0000-0000-0000-000000000001",
        date = "2026-04-23",
        steps = 1600,
        avgHeartRate = 112,
        avgSpo2Pct = 88,
    )

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun postDailySummary_sendsSignedJsonBody() {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"ok":true,"date":"2026-04-23","detection":{"anomaly_count":1,"alerted":false,"severities":["MEDIUM"]}}"""
            )
        )

        val client = WebhookClient(
            baseUrl = server.url("/").toString().trimEnd('/'),
            secret = "real-secret-abc",
        )
        val result = client.postDailySummary(sampleSummary)

        assertTrue("expected ok=true for 200 response, got status=${result.status}", result.ok)
        assertEquals(200, result.status)

        val recorded = server.takeRequest()
        assertEquals("POST", recorded.method)
        assertEquals("/wearable/samsung/webhook", recorded.path)
        assertEquals("application/json; charset=utf-8", recorded.getHeader("Content-Type"))

        val signature = recorded.getHeader("X-Saath-Signature")
        assertNotNull("X-Saath-Signature header missing", signature)
        assertFalse("signature should not contain whitespace: $signature", signature!!.any { it.isWhitespace() })

        val body = recorded.body.readUtf8()
        assertTrue("body missing senior_id: $body", body.contains("\"senior_id\""))
        assertTrue("body missing steps: $body", body.contains("\"steps\":1600"))
        // Omitted nulls never appear on the wire
        assertFalse("null hrv_rmssd leaked onto wire: $body", body.contains("hrv_rmssd"))

        // The exact HMAC the backend will verify against
        val expectedSig = HmacSigner.sign("real-secret-abc", body.toByteArray(Charsets.UTF_8))
        assertEquals(
            "signature header does not match recomputed HMAC over the body — " +
                "means backend HMAC verify would reject this request",
            expectedSig,
            signature,
        )
    }

    @Test
    fun postDailySummary_401_returnsFailure() {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"invalid signature"}"""))

        val client = WebhookClient(
            baseUrl = server.url("/").toString().trimEnd('/'),
            secret = "wrong",
        )
        val result = client.postDailySummary(sampleSummary)

        assertFalse("401 must not report ok", result.ok)
        assertEquals(401, result.status)
    }

    @Test
    fun postDailySummary_500_returnsFailure() {
        server.enqueue(MockResponse().setResponseCode(500))

        val client = WebhookClient(
            baseUrl = server.url("/").toString().trimEnd('/'),
            secret = "any",
        )
        val result = client.postDailySummary(sampleSummary)

        assertFalse(result.ok)
        assertEquals(500, result.status)
    }
}
