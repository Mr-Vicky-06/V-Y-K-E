"""M2 Audio Pipeline Verification:
Runs end-to-end audio pipeline on speech audio ('open notepad').
Reports transcript, ASR latency, routing latency, policy gate decision, and tool result.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from voicecore.asr.whistle import WhistleASR
from voicecore.config import VoiceCoreConfig
from voicecore.events import EventBus
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry


def run_audio_pipeline(wav_path: str, dry_run: bool = True):
    config = VoiceCoreConfig.from_toml("config/voicecore.toml")
    registry = ToolRegistry()

    if dry_run:
        def open_app_dry(app_name: str) -> dict:
            return open_app(app_name, dry_run=True)
        open_app_dry.__name__ = "open_app"
        registry.register(open_app_dry, tier="T1", name="open_app")
    else:
        registry.register(open_app, tier="T1", name="open_app")

    gate = PolicyGate(config=config.policy, registry=registry)
    event_bus = EventBus()

    # Track events
    events_log = []
    event_bus.subscribe_all(lambda e: events_log.append(e))

    router = NeedleRouter(registry=registry, stateless=True)
    asr = WhistleASR(config=config.asr, debug_config=config.debug)

    assistant = Assistant(
        router=router,
        registry=registry,
        policy_gate=gate,
        asr=asr,
        config=config,
        event_bus=event_bus,
    )

    print(f"Executing speech pipeline on: {wav_path}")
    t0 = time.perf_counter()
    results = assistant.run_audio(wav_path)
    total_ms = (time.perf_counter() - t0) * 1000.0

    print("\n--- Pipeline Execution Evidence ---")
    for e in events_log:
        print(f"  {type(e).__name__}: {vars(e)}")

    print(f"\nTotal Pipeline Time: {total_ms:.1f}ms")
    print(f"Results: {results}")

    return results


if __name__ == "__main__":
    audio_file = "tests/test_data/audio/open_notepad_16k.wav"
    run_audio_pipeline(audio_file, dry_run=True)
