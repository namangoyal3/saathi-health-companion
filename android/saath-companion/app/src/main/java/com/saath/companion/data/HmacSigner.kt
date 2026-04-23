package com.saath.companion.data

import java.util.Base64
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * HMAC-SHA256 signer matching backend/app/api/wearable.py `_verify_hmac`.
 *
 * Backend computes:
 *   base64(hmac_sha256(secret_bytes, body_bytes))
 * and compares with `hmac.compare_digest` against the `X-Saath-Signature` header.
 *
 * Uses `java.util.Base64` rather than `android.util.Base64` so the signer
 * is JVM-testable (pure unit tests) without Robolectric, and produces the
 * same single-line encoding Python emits.
 */
object HmacSigner {

    private const val HMAC_ALG = "HmacSHA256"

    fun sign(secret: String, body: ByteArray): String {
        val mac = Mac.getInstance(HMAC_ALG)
        mac.init(SecretKeySpec(secret.toByteArray(Charsets.UTF_8), HMAC_ALG))
        val digest = mac.doFinal(body)
        return Base64.getEncoder().encodeToString(digest)
    }
}
