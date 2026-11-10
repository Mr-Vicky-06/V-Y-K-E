"""Whistle ASR implementation wrapping Cactus Compute."""
from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, List, Optional
import wave

import numpy as np

from voicecore.asr.base import ASR, Transcript
from voicecore.config import ASRConfig, DebugConfig
from voicecore.engine import transcribe as engine_transcribe


class WhistleASR(ASR):
    """Offline speech-to-text implementation using Cactus Whistle (16.9 MB)."""

    def __init__(
        self,
        config: Optional[ASRConfig] = None,
        debug_config: Optional[DebugConfig] = None,
        weights: Optional[str] = None,
    ) -> None:
        self.config = config or ASRConfig()
        self.debug_config = debug_config or DebugConfig()
        self.weights = weights

    def transcribe(self, audio: Any) -> Transcript:
        """Transcribe speech audio into a Transcript dataclass.

        Args:
            audio: WAV file path (str or Path) or numpy array (16 kHz mono float32/int16).

        Returns:
            Transcript containing transcribed text, detected/target language, and latency.
        """
        t0 = time.perf_counter()

        # Handle debug audio saving if requested
        if self.debug_config.save_audio and isinstance(audio, (str, Path)) and os.path.exists(audio):
            # Audio is already on disk
            pass
        elif self.debug_config.save_audio and isinstance(audio, np.ndarray):
            self._save_debug_audio(audio)

        # Execute transcription via engine
        keywords = self.config.keywords if self.config.keywords else None
        language = self.config.language if self.config.language else "en"

        try:
            raw_out = engine_transcribe(
                audio=audio,
                language=language,
                keywords=keywords,
                weights=self.weights,
            )
        except Exception as e:
            asr_ms = (time.perf_counter() - t0) * 1000.0
            return Transcript(text="", language=language, asr_ms=asr_ms)

        asr_ms = (time.perf_counter() - t0) * 1000.0
        text = str(raw_out.get("text", "")).strip()
        detected_lang = str(raw_out.get("language", language) or language)

        return Transcript(
            text=text,
            language=detected_lang,
            asr_ms=asr_ms,
        )

    def _save_debug_audio(self, samples: np.ndarray) -> None:
        """Save captured numpy samples to disk for debugging only when explicitly enabled."""
        try:
            os.makedirs("debug_audio", exist_ok=True)
            filename = f"debug_audio/capture_{int(time.time()*1000)}.wav"
            # Scale float32 to int16 PCM
            if samples.dtype == np.float32:
                int16_samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                int16_samples = samples.astype(np.int16)

            with wave.open(filename, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(int16_samples.tobytes())
        except Exception:
            pass

