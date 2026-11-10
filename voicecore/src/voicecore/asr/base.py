"""ASR protocol definition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Transcript:
    """ASR transcription result."""
    text: str = ""
    language: str = "en"
    asr_ms: float = 0.0


class ASR(Protocol):
    """Protocol for Speech-to-Text implementations."""

    def transcribe(self, audio: Any) -> Transcript:
        """Transcribe audio (file path or in-memory samples) into text."""
        ...
