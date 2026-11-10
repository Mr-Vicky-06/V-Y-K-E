"""Configuration loader and validator for VoiceCore."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class AudioConfig:
    hotkey: str = "ctrl+alt+space"
    max_seconds: int = 30


@dataclass
class ASRConfig:
    language: str = "en"
    keywords: List[str] = field(default_factory=list)


@dataclass
class PolicyConfig:
    act_threshold: float = 0.80
    confirm_threshold: float = 0.50
    confirm_timeout_s: int = 10


@dataclass
class SearchConfig:
    roots: List[str] = field(default_factory=list)
    max_results: int = 10


@dataclass
class DebugConfig:
    save_audio: bool = False
    log_jsonl: bool = True


@dataclass
class VoiceCoreConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)

    @classmethod
    def from_toml(cls, path: str | Path) -> VoiceCoreConfig:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with file_path.open("rb") as f:
            data = tomllib.load(f)

        audio = AudioConfig(**data.get("audio", {}))
        asr = ASRConfig(**data.get("asr", {}))
        policy = PolicyConfig(**data.get("policy", {}))
        search = SearchConfig(**data.get("search", {}))
        debug = DebugConfig(**data.get("debug", {}))

        # Basic validation
        if not (0.0 <= policy.confirm_threshold <= policy.act_threshold <= 1.0):
            raise ValueError(
                f"Invalid policy thresholds: confirm_threshold ({policy.confirm_threshold}) "
                f"must be <= act_threshold ({policy.act_threshold}) within [0.0, 1.0]"
            )

        return cls(audio=audio, asr=asr, policy=policy, search=search, debug=debug)

