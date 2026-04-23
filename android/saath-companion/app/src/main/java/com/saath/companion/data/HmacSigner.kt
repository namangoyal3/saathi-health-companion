package com.saath.companion.data

import android.util.Base64
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * HMAC-SHA256 signer matching backend/app/api/wearable.py `_verify_hmac`.
 *
 * Backend computes:
 *   base64(hmac_sha256(secret_bytes, body_bytes))
 * and compares with `hmac.compare_digest` against the `X-Saath-Signature` header.
 *
 * Android's `Base64.NO_WRAP` avoids line breaks that would mismatch Python's
 * `base64.b64encode(...).decode()` single-line output.
 */
object HmacSigner {

    private const val HMAC_ALG = "HmacSHA256"

    fun sign(secret: String, body: ByteArray): String {
        val mac = Mac.getInstance(HMAC_ALG)
        mac.init(SecretKeySpec(secret.toByteArray(Charsets.UTF_8), HMAC_ALG))
        val digest = mac.doFinal(body)
        return Base64.encodeToString(digest, Base64.NO_WRAP)
    }
}
