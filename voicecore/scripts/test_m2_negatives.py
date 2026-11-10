"""M2 Acceptance & Negative Audio Evaluation:
Runs 3 repeats each of silence, keyboard noise, and a 10s music clip.
Verifies that zero actions are executed across all negative runs.
"""
import json
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


def run_negative_tests():
    config = VoiceCoreConfig()
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app")

    gate = PolicyGate(config=config.policy, registry=registry)
    event_bus = EventBus()
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

    audio_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "test_data", "audio")
    test_files = [
        ("silence", os.path.join(audio_dir, "silence.wav"), 3),
        ("keyboard_noise", os.path.join(audio_dir, "keyboard_noise.wav"), 3),
        ("music_clip_10s", os.path.join(audio_dir, "music_clip_10s.wav"), 3),
    ]

    total_runs = 0
    total_actions_fired = 0
    detailed_results = []

    print("=" * 70)
    print(" VoiceCore Milestone M2: Negative Audio Evaluation (3 Repeats Each)")
    print(" Target: ZERO tool executions across all negative clips")
    print("=" * 70)

    for category, filepath, repeats in test_files:
        print(f"\n--- Testing Category: {category} (File: {os.path.basename(filepath)}) ---")
        for rep in range(1, repeats + 1):
            total_runs += 1
            t0 = time.perf_counter()
            results = assistant.run_audio(filepath)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # Count actual tool executions
            actions_executed = [r for r in results if r.get("status") == "executed"]
            if actions_executed:
                total_actions_fired += len(actions_executed)

            entry = {
                "category": category,
                "repeat": rep,
                "elapsed_ms": elapsed_ms,
                "pipeline_results": results,
                "actions_executed_count": len(actions_executed),
            }
            detailed_results.append(entry)

            print(f"  [Run {rep}/3] {category}: {elapsed_ms:.1f}ms elapsed | Actions fired: {len(actions_executed)}")
            if results:
                print(f"             Pipeline return: {results}")

    print("\n" + "=" * 70)
    print(f" Summary: {total_runs} negative runs evaluated.")
    print(f" Total Tool Actions Fired: {total_actions_fired}")
    passed = (total_actions_fired == 0)
    print(f" Result: {'PASS (Zero actions fired)' if passed else 'FAIL (Actions were executed)'}")
    print("=" * 70)

    # Save artifact
    out_json = os.path.join(os.path.dirname(__file__), "m2_negative_audio_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_runs": total_runs,
                "total_actions_fired": total_actions_fired,
                "passed": passed,
                "runs": detailed_results,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"Detailed results saved to: {out_json}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(run_negative_tests())

