"""M2 Negative Audio Evaluation -- Verbose Edition.

For every run reports:
  - Whistle transcript (text + asr_ms)
  - Needle route (calls, confidence, negation, ungrounded, nlu_ms)
  - Gate decision for each call
  - Whether any action fired (must be zero across all runs)

Usage:
    python scripts/test_m2_negatives_verbose.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from voicecore.asr.whistle import WhistleASR
from voicecore.config import ASRConfig, DebugConfig, VoiceCoreConfig
from voicecore.events import (
    EventBus,
    GateEvent,
    RouteEvent,
    TranscriptEvent,
    NoSpeechEvent,
)
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry


def run() -> int:
    config = VoiceCoreConfig()
    # Enable keyword biasing (matches production config)
    config.asr = ASRConfig(keywords=["notepad", "calculator"])

    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app")

    gate = PolicyGate(config=config.policy, registry=registry)
    bus = EventBus()
    router = NeedleRouter(registry=registry, stateless=True)
    asr = WhistleASR(config=config.asr, debug_config=config.debug)

    # Collect events per-run
    run_events: List[Dict[str, Any]] = []

    def on_event(e: Any) -> None:
        run_events.append(e)

    bus.subscribe_all(on_event)

    assistant = Assistant(
        router=router,
        registry=registry,
        policy_gate=gate,
        asr=asr,
        config=config,
        event_bus=bus,
    )

    audio_dir = Path(__file__).resolve().parent.parent / "tests" / "test_data" / "audio"
    test_cases = [
        ("silence",        audio_dir / "silence.wav",         3),
        ("keyboard_noise", audio_dir / "keyboard_noise.wav",  3),
        ("music_clip_10s", audio_dir / "music_clip_10s.wav",  3),
    ]

    print("=" * 70)
    print(" VoiceCore M2 Negative Evaluation  —  Verbose Transcript+Route Log")
    print(" Keyword biasing: ['notepad', 'calculator']")
    print(" Target: ZERO tool executions across all 9 runs")
    print("=" * 70)

    total_actions = 0

    for category, filepath, repeats in test_cases:
        print(f"\n{'─'*70}")
        print(f" Category: {category}   file: {filepath.name}")
        print(f"{'─'*70}")

        for rep in range(1, repeats + 1):
            run_events.clear()
            t0 = time.perf_counter()
            results = assistant.run_audio(str(filepath))
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            actions_fired = [r for r in results if r.get("status") == "executed"]
            total_actions += len(actions_fired)

            # Decode captured events
            transcript_text = "<empty>"
            asr_ms = 0.0
            route_calls: List[Any] = []
            route_conf = 0.0
            route_nlu_ms = 0.0
            route_neg = False
            route_ung: List[str] = []
            gate_decisions: List[str] = []

            for ev in run_events:
                if isinstance(ev, TranscriptEvent):
                    transcript_text = ev.text
                    asr_ms = ev.asr_ms
                elif isinstance(ev, NoSpeechEvent):
                    transcript_text = "<silence/empty>"
                elif isinstance(ev, RouteEvent):
                    route_calls = ev.calls
                    route_conf = ev.confidence
                    route_nlu_ms = ev.nlu_ms
                    route_neg = ev.negation
                    route_ung = list(ev.ungrounded or [])
                elif isinstance(ev, GateEvent):
                    gate_decisions.append(f"{ev.call.get('name')}→{ev.decision}({ev.reason})")

            status = "✓ PASS" if not actions_fired else "✗ FAIL"
            print(f"\n  Run {rep}/3  [{status}]  total={elapsed_ms:.0f}ms")
            print(f"    ASR  : {asr_ms:.1f}ms  transcript='{transcript_text}'")
            print(f"    NLU  : {route_nlu_ms:.1f}ms  confidence={route_conf:.4f}  "
                  f"negation={route_neg}  ungrounded={route_ung}")
            if route_calls:
                print(f"    calls: {route_calls}")
            else:
                print(f"    calls: []  (no tool call proposed)")
            if gate_decisions:
                print(f"    gate : {'; '.join(gate_decisions)}")
            if actions_fired:
                print(f"    *** ACTIONS FIRED: {actions_fired} ***")

    print(f"\n{'='*70}")
    print(f" Total negative runs:    9")
    print(f" Total actions fired:   {total_actions}")
    result = "PASS ✓" if total_actions == 0 else "FAIL ✗"
    print(f" Result: {result}")
    print("=" * 70)
    return 0 if total_actions == 0 else 1


if __name__ == "__main__":
    sys.exit(run())

