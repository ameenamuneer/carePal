"""
Wall-clock energy-based end-of-speech (EOS) detector.

This is a source-agnostic Voice Activity Detector used to segment a live
microphone stream into utterances. It decides end-of-speech purely from the
acoustic signal — speech energy seen, then a sustained run of silence —
evaluated on a WALL CLOCK, not on frame arrival. A real mic streams continuous
(including quiet) frames, so trailing silence is measured as elapsed real time
since the last speech-energy frame.

Mirrors the reference JS `createEosDetector`. One detector instance handles ONE
utterance window; create a fresh one per listening window.
"""

import time
from typing import Optional

import numpy as np


def rms_int16(frame: np.ndarray) -> float:
    """RMS amplitude of an int16 buffer, normalized to 0..1."""
    if frame is None or frame.size == 0:
        return 0.0
    x = frame.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x)))


def _now_ms() -> float:
    return time.monotonic() * 1000.0


class EnergyEosDetector:
    """
    Stateful detector for ONE utterance window.

    - push_audio(): called for every arriving frame; energy bookkeeping only.
    - check_eos(): called on a wall-clock timer (e.g. every 100 ms). Returns
      True exactly once per utterance, when speech has been observed and
      `silence_ms` of real time has elapsed since the last speech-energy frame.
    - saw_speech: guards against transcribing pure silence.
    """

    def __init__(
        self,
        rate: int = 16000,
        energy_threshold: float = 0.012,
        min_speech_ms: float = 200.0,
        silence_ms: float = 700.0,
    ):
        self.rate = rate
        self.energy_threshold = energy_threshold
        self.min_speech_ms = min_speech_ms
        self.silence_ms = silence_ms

        self._speech_ms = 0.0
        self._has_speech = False
        self._last_speech_at = 0.0
        self._fired = False

    def push_audio(self, frame: np.ndarray, now: Optional[float] = None) -> None:
        """Feed a real int16 frame as it arrives (energy accounting only)."""
        if self._fired or frame is None or frame.size == 0:
            return
        if now is None:
            now = _now_ms()
        dur_ms = (frame.size / self.rate) * 1000.0
        if rms_int16(frame) >= self.energy_threshold:
            self._speech_ms += dur_ms
            self._last_speech_at = now
            if self._speech_ms >= self.min_speech_ms:
                self._has_speech = True

    def check_eos(self, now: Optional[float] = None) -> bool:
        """Wall-clock decision. True exactly once when the utterance ends."""
        if self._fired or not self._has_speech:
            return False
        if now is None:
            now = _now_ms()
        if now - self._last_speech_at >= self.silence_ms:
            self._fired = True
            return True
        return False

    @property
    def saw_speech(self) -> bool:
        return self._has_speech
