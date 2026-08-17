"""
ElevenLabs Scribe speech-to-text (prerecorded / utterance upload).

Wraps a finished utterance's 16 kHz mono PCM16 in a WAV container and POSTs it
to the ElevenLabs speech-to-text endpoint. Automatic language detection is
achieved by OMITTING `language_code` entirely.

Endpoint: POST https://api.elevenlabs.io/v1/speech-to-text
Auth:     xi-api-key: <ELEVENLABS_API_KEY>
Body:     multipart/form-data { model_id, file }
Response: { language_code, language_probability, text, words: [...] } -> use `text`

Note: `scribe_v2_realtime` is a websocket streaming model and is rejected by
this REST endpoint; for utterance uploads use `scribe_v2`.
"""

import io
import os
import wave
import logging
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def get_elevenlabs_key() -> Optional[str]:
    """Resolve the API key from the usual environment variables."""
    return (
        os.environ.get("ELEVENLABS_API_KEY")
        or os.environ.get("ELEVEN_API_KEY")
        or os.environ.get("XI_API_KEY")
    )


def has_elevenlabs_key() -> bool:
    return bool(get_elevenlabs_key())


def pcm16_to_wav_bytes(int16: np.ndarray, rate: int = 16000) -> bytes:
    """Wrap mono int16 PCM in a minimal WAV so any sample rate is accepted."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(np.ascontiguousarray(int16, dtype=np.int16).tobytes())
    return buf.getvalue()


def transcribe_elevenlabs(
    int16: np.ndarray,
    rate: int = 16000,
    model_id: str = "scribe_v2",
    timeout: float = 20.0,
    api_key: Optional[str] = None,
    tag_audio_events: bool = True,
) -> str:
    """
    Transcribe a finished utterance. Blocking (uses `requests`); call via
    asyncio.to_thread from async code. Returns the transcript text (may be '').

    `tag_audio_events` (default True) controls whether Scribe annotates
    non-speech events like "[Background noise]". Set it False when the transcript
    is used only to decide whether real speech is present (e.g. barge-in gating),
    so noise yields an empty string instead of a bracket tag.
    """
    key = api_key or get_elevenlabs_key()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    if int16 is None or int16.size == 0:
        return ""

    wav = pcm16_to_wav_bytes(int16, rate)
    # Automatic language detection = do NOT send language_code.
    data = {
        "model_id": model_id,
        "tag_audio_events": "true" if tag_audio_events else "false",
    }
    files = {"file": ("audio.wav", wav, "audio/wav")}

    # Do NOT set Content-Type manually — requests sets the multipart boundary.
    resp = requests.post(
        ELEVENLABS_STT_URL,
        headers={"xi-api-key": key},
        data=data,
        files=files,
        timeout=timeout,
    )
    if not resp.ok:
        detail = ""
        try:
            detail = resp.text[:200]
        except Exception:
            pass
        raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {detail}")

    j = resp.json()
    return str(j.get("text") or "").strip()
