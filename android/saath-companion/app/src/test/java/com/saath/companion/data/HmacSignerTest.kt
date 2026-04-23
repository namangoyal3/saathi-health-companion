package com.saath.companion.data

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Verifies HmacSigner produces the exact same base64-encoded HMAC-SHA256
 * that the backend's `_verify_hmac` expects.
 *
 * The expected signature below was computed with Python:
 *   python -c "import hmac,hashlib,base64; \
 *              print(base64.b64encode(hmac.new(b'real-secret-abc', \
 *              b'{\"senior_id\":\"00000000-0000-0000-0000-000000000001\",\"date\":\"2026-04-23\",\"steps\":1600}', \
 *              hashlib.sha256).digest()).decode())"
 * That value is hardcoded below so any future change to HmacSigner that
 * silently alters the signature (e.g. someone flips Base64.DEFAULT for
 * Base64.NO_WRAP, or swaps the digest algorithm) fails this test.
 */
class HmacSignerTest {

    @Test
    fun sign_matchesPythonReferenceOutput() {
        val secret = "real-secret-abc"
        val body = """{"senior_id":"00000000-0000-0000-0000-000000000001","date":"2026-04-23","steps":1600}"""
        val expected = "wq9jOPsNynxhETxOuwIe1r6hcJQIITKVmhCRk0C1jiQ="

        val actual = HmacSigner.sign(secret, body.toByteArray(Charsets.UTF_8))

        assertEquals(expected, actual)
    }

    @Test
    fun sign_differentBody_producesDifferentSignature() {
        val secret = "k"
        val sig1 = HmacSigner.sign(secret, "a".toByteArray())
        val sig2 = HmacSigner.sign(secret, "b".toByteArray())
        assert(sig1 != sig2) { "HMAC of different bodies must differ" }
    }

    @Test
    fun sign_differentSecrets_producesDifferentSignature() {
        val body = "same body".toByteArray()
        val sig1 = HmacSigner.sign("secret1", body)
        val sig2 = HmacSigner.sign("secret2", body)
        assert(sig1 != sig2) { "HMAC with different secrets must differ" }
    }

    @Test
    fun sign_output_hasNoNewline() {
        val sig = HmacSigner.sign("k", "hello world".toByteArray())
        assert(!sig.contains('\n')) { "Signature must be NO_WRAP base64 — got: $sig" }
        assert(!sig.contains('\r')) { "Signature must not contain CR — got: $sig" }
    }
}
