"""TTS rendering — Google Neural2 (Tamil/English) + Sarvam Bulbul v3 (Hindi).

Audio format: 8 kHz 16-bit PCM WAV — required by Exotel/Twilio SIP.
Cache: R2 at /ivr/tts/cached/<sha256_hex>.wav. Skips re-render on cache hit.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_CACHE_DIR = Path("/tmp/saath_tts_cache")


def _local_cache_path(text: str, lang: str) -> Path:
    h = hashlib.sha256(f"{lang}:{text}".encode()).hexdigest()[:24]
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{h}.wav"


def _r2_cache_key(text: str, lang: str) -> str:
    h = hashlib.sha256(f"{lang}:{text}".encode()).hexdigest()[:24]
    return f"ivr/tts/cached/{h}.wav"


def _check_r2_cache(r2_key: str) -> bytes | None:
    if not (settings.r2_account_id and settings.r2_access_key_id):
        return None
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        resp = s3.get_object(Bucket=settings.r2_bucket, Key=r2_key)
        return resp["Body"].read()  # type: ignore[no-any-return]
    except Exception:
        return None


def _put_r2_cache(r2_key: str, wav_bytes: bytes) -> None:
    if not (settings.r2_account_id and settings.r2_access_key_id):
        return
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        s3.put_object(
            Bucket=settings.r2_bucket, Key=r2_key, Body=wav_bytes, ContentType="audio/wav"
        )
    except Exception as exc:
        log.warning("tts_r2_cache_write_failed key=%s err=%s", r2_key, exc)


def _synthesize_tamil(text: str) -> bytes:
    """Google Cloud Neural2 ta-IN-Neural2-A, 8kHz PCM16."""
    if settings.google_application_credentials:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS", settings.google_application_credentials
        )
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        resp = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(
                language_code="ta-IN",
                name="ta-IN-Neural2-A",
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                speaking_rate=0.9,
                pitch=0.0,
            ),
        )
        return resp.audio_content  # type: ignore[no-any-return]
    except ImportError:
        log.warning("google-cloud-texttospeech not installed; returning silent WAV")
        return _silent_wav()


def _synthesize_hindi(text: str) -> bytes:
    """Sarvam Bulbul v3 hi-IN simran, 8kHz PCM16."""
    if not settings.sarvam_api_key:
        log.warning("SARVAM_API_KEY not set; returning silent WAV")
        return _silent_wav()

    r = httpx.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={"api-subscription-key": settings.sarvam_api_key},
        json={
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": "simran",
            "pitch": 0,
            "pace": 0.9,
            "loudness": 1.2,
            "model": "bulbul:v3",
        },
        timeout=15.0,
    )
    r.raise_for_status()
    return base64.b64decode(r.json()["audios"][0])


def _synthesize_english(text: str) -> bytes:
    """Google Cloud Neural2 en-IN-Neural2-D, 8kHz PCM16."""
    if settings.google_application_credentials:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS", settings.google_application_credentials
        )
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        resp = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(
                language_code="en-IN",
                name="en-IN-Neural2-D",
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                speaking_rate=0.9,
                pitch=0.0,
            ),
        )
        return resp.audio_content  # type: ignore[no-any-return]
    except ImportError:
        log.warning("google-cloud-texttospeech not installed; returning silent WAV")
        return _silent_wav()


def _silent_wav(duration_ms: int = 2000) -> bytes:
    """Minimal valid 8kHz 16-bit PCM WAV with silence (for dev/test)."""
    num_samples = 8000 * duration_ms // 1000
    pcm = b"\x00\x00" * num_samples  # 16-bit silence
    data_len = len(pcm)
    header = (
        b"RIFF"
        + (36 + data_len).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")  # PCM
        + (1).to_bytes(2, "little")  # mono
        + (8000).to_bytes(4, "little")  # sample rate
        + (16000).to_bytes(4, "little")  # byte rate
        + (2).to_bytes(2, "little")  # block align
        + (16).to_bytes(2, "little")  # bits per sample
        + b"data"
        + data_len.to_bytes(4, "little")
    )
    return header + pcm


def render_tts_tamil(text: str, out_path: str) -> None:
    _render(text, "ta", out_path, _synthesize_tamil)


def render_tts_hindi(text: str, out_path: str) -> None:
    _render(text, "hi", out_path, _synthesize_hindi)


def render_tts_english(text: str, out_path: str) -> None:
    _render(text, "en", out_path, _synthesize_english)


def _render(
    text: str,
    lang: str,
    out_path: str,
    synthesizer: object,
) -> None:
    from collections.abc import Callable

    synth: Callable[[str], bytes] = synthesizer  # type: ignore[assignment]
    local = _local_cache_path(text, lang)
    r2_key = _r2_cache_key(text, lang)

    if local.exists():
        Path(out_path).write_bytes(local.read_bytes())
        return

    cached = _check_r2_cache(r2_key)
    if cached:
        local.write_bytes(cached)
        Path(out_path).write_bytes(cached)
        return

    wav = synth(text)
    local.write_bytes(wav)
    _put_r2_cache(r2_key, wav)
    Path(out_path).write_bytes(wav)
    log.info("tts_rendered lang=%s bytes=%d", lang, len(wav))


def get_tts_url(text: str, lang: str, *, call_id: str) -> str:
    """Return a URL that serves the pre-rendered TTS audio for this text.

    In production this would be an R2 signed URL; in dev it's a local endpoint.
    """
    h = hashlib.sha256(f"{lang}:{text}".encode()).hexdigest()[:24]
    return f"{settings.app_base_url}/ivr/audio/{h}.wav?call_id={call_id}"
