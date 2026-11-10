"""Engine adapter for Cactus Compute runtime (Whistle ASR & Needle 3 NLU).

All engine-level dependencies and privacy controls are isolated here. No other
module in voicecore should import the raw underlying engine package directly.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Union

# Enforce strict privacy guardrails prior to engine import
os.environ.setdefault("CACTUS_TELEMETRY", "0")
os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")

import cactus

__version__ = getattr(cactus, "__version__", "4.1.0")

# Primary decorator for registering tools with the engine
tool = cactus.tool

# Router agent class (Needle 3)
NeedleAgent = cactus.Cactus

# ASR class & standalone function (Whistle)
Whistle = cactus.Whistle
transcribe = cactus.transcribe

# Thread tuning API
set_threads = getattr(cactus, "set_threads", lambda n: None)

__all__ = [
    "tool",
    "NeedleAgent",
    "Whistle",
    "transcribe",
    "set_threads",
    "__version__",
]

