"""Push-to-talk audio capture using sounddevice with native rate capture and soxr resampling."""
from __future__ import annotations

import logging
import threading
from typing import Any, List, Optional, Tuple, Union

import numpy as np
import sounddevice as sd
import soxr

from voicecore.config import AudioConfig

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000


def resolve_input_device(device_spec: Optional[Union[str, int]] = None) -> Tuple[int, str, float]:
    """Resolve an authorized hardware audio input device, excluding 'Microsoft Sound Mapper'.

    Args:
        device_spec: Device index (int) or name substring (str). If None/empty, auto-detects.

    Returns:
        Tuple of (device_index, device_name, native_sample_rate)
    """
    devices = sd.query_devices()

    # 1. If explicit integer index is specified
    if isinstance(device_spec, int):
        if 0 <= device_spec < len(devices):
            d = devices[device_spec]
            if d.get("max_input_channels", 0) > 0:
                return device_spec, str(d["name"]), float(d.get("default_samplerate", 44100.0))
        raise ValueError(f"Invalid input device index: {device_spec}")

    # 2. If explicit string substring is specified
    if isinstance(device_spec, str) and device_spec.strip():
        query = device_spec.lower().strip()
        for idx, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0 and query in str(d["name"]).lower():
                return idx, str(d["name"]), float(d.get("default_samplerate", 44100.0))
        raise ValueError(f"No audio input device matching '{device_spec}' found")

    # 3. Default fallback: check system default device if not Microsoft Sound Mapper
    default_in = sd.default.device[0]
    if default_in is not None and default_in >= 0 and default_in < len(devices):
        d = devices[default_in]
        if d.get("max_input_channels", 0) > 0 and "sound mapper" not in str(d["name"]).lower():
            return default_in, str(d["name"]), float(d.get("default_samplerate", 44100.0))

    # 4. Search for first non-Sound Mapper input device
    for idx, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0 and "sound mapper" not in str(d["name"]).lower():
            return idx, str(d["name"]), float(d.get("default_samplerate", 44100.0))

    # 5. Last resort fallback to default index
    idx = default_in if (default_in is not None and default_in >= 0) else 0
    d = devices[idx] if idx < len(devices) else {"name": "Default Input", "default_samplerate": 44100.0}
    return idx, str(d["name"]), float(d.get("default_samplerate", 44100.0))


class AudioCapture:
    """Manages microphone audio recording at native device rate, resampling to 16 kHz with soxr."""

    def __init__(self, config: Optional[AudioConfig] = None) -> None:
        self.config = config or AudioConfig()
        self.target_rate = TARGET_SAMPLE_RATE

        device_idx, device_name, native_rate = resolve_input_device(self.config.device)
        self.device_index = device_idx
        self.device_name = device_name
        self.native_rate = int(native_rate)

        # Enforce 30 s cap based on native rate
        self.max_native_samples = int(self.config.max_seconds * self.native_rate)

        self._lock = threading.Lock()
        self._frames: List[np.ndarray] = []
        self._total_native_samples = 0
        self._is_recording = False
        self._stream: Optional[sd.InputStream] = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def _callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags) -> None:
        with self._lock:
            if not self._is_recording:
                return

            channel_data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            self._frames.append(channel_data)
            self._total_native_samples += len(channel_data)

            if self._total_native_samples >= self.max_native_samples:
                self._is_recording = False

    def start_capture(self) -> None:
        """Start capturing audio from the resolved input device."""
        with self._lock:
            if self._is_recording:
                return

            self._frames.clear()
            self._total_native_samples = 0
            self._is_recording = True

            try:
                self._stream = sd.InputStream(
                    samplerate=self.native_rate,
                    device=self.device_index,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                )
                self._stream.start()
            except Exception as e:
                self._is_recording = False
                self._stream = None
                raise RuntimeError(
                    f"Failed to start audio stream on device '{self.device_name}' (idx {self.device_index}) "
                    f"at {self.native_rate}Hz: {e}"
                ) from e

    def stop_capture(self) -> np.ndarray:
        """Stop capturing and return the recorded audio resampled to 16 kHz mono float32."""
        stream_to_stop = None
        with self._lock:
            if not self._is_recording and not self._frames:
                return np.zeros(0, dtype=np.float32)

            self._is_recording = False
            stream_to_stop = self._stream
            self._stream = None

            if not self._frames:
                return np.zeros(0, dtype=np.float32)

            raw_audio = np.concatenate(self._frames, axis=0).astype(np.float32)
            if len(raw_audio) > self.max_native_samples:
                raw_audio = raw_audio[: self.max_native_samples]

            # Immediate in-memory discard of chunk list
            self._frames.clear()
            self._total_native_samples = 0

        if stream_to_stop is not None:
            try:
                stream_to_stop.stop()
                stream_to_stop.close()
            except Exception:
                pass

        if len(raw_audio) == 0:
            return np.zeros(0, dtype=np.float32)

        # Resample to 16 kHz if device native rate is different
        if self.native_rate != self.target_rate:
            resampled = soxr.resample(raw_audio, in_rate=self.native_rate, out_rate=self.target_rate)
            return resampled.astype(np.float32)

        return raw_audio

    def close(self) -> None:
        self.stop_capture()
