"""Push-to-talk audio capture using sounddevice."""
from __future__ import annotations

import threading
import time
from typing import List, Optional

import numpy as np
import sounddevice as sd

from voicecore.config import AudioConfig


class AudioCapture:
    """Manages thread-safe microphone audio recording at 16 kHz mono with a duration cap."""

    def __init__(self, config: Optional[AudioConfig] = None, sample_rate: int = 16000) -> None:
        self.config = config or AudioConfig()
        self.sample_rate = sample_rate
        self.max_samples = int(self.config.max_seconds * self.sample_rate)

        self._lock = threading.Lock()
        self._frames: List[np.ndarray] = []
        self._total_samples = 0
        self._is_recording = False
        self._stream: Optional[sd.InputStream] = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def _callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags) -> None:
        """Audio stream callback running in sounddevice's audio thread."""
        with self._lock:
            if not self._is_recording:
                return

            # Append mono channel copy
            channel_data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            self._frames.append(channel_data)
            self._total_samples += len(channel_data)

            # Enforce 30s max duration cap
            if self._total_samples >= self.max_samples:
                self._is_recording = False

    def start_capture(self) -> None:
        """Start capturing audio from default input device."""
        with self._lock:
            if self._is_recording:
                return

            self._frames.clear()
            self._total_samples = 0
            self._is_recording = True

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                )
                self._stream.start()
            except Exception as e:
                self._is_recording = False
                self._stream = None
                raise RuntimeError(f"Failed to start audio input stream: {e}") from e

    def stop_capture(self) -> np.ndarray:
        """Stop capturing and return the recorded 16 kHz mono float32 audio array."""
        stream_to_stop = None
        with self._lock:
            if not self._is_recording and not self._frames:
                return np.zeros(0, dtype=np.float32)

            self._is_recording = False
            stream_to_stop = self._stream
            self._stream = None

            if not self._frames:
                return np.zeros(0, dtype=np.float32)

            # Concatenate collected chunks
            audio_data = np.concatenate(self._frames, axis=0).astype(np.float32)
            # Cap at max_samples if slightly exceeded
            if len(audio_data) > self.max_samples:
                audio_data = audio_data[: self.max_samples]

            # In-memory discard: clear internal references immediately
            self._frames.clear()
            self._total_samples = 0

        if stream_to_stop is not None:
            try:
                stream_to_stop.stop()
                stream_to_stop.close()
            except Exception:
                pass

        return audio_data

    def close(self) -> None:
        """Release audio resources."""
        self.stop_capture()
