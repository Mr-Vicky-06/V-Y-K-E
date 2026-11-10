"""VoiceCore CLI entrypoint.

Supports:
    python -m voicecore --text "open notepad"
    python -m voicecore --mic
    python -m voicecore --text "open notepad" --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
import threading
import time

from voicecore.asr.whistle import WhistleASR
from voicecore.audio.capture import AudioCapture
from voicecore.audio.hotkey import HotkeyListener
from voicecore.config import VoiceCoreConfig
from voicecore.events import (
    ConfirmRequestEvent,
    DoneEvent,
    ErrorEvent,
    Event,
    EventBus,
    GateEvent,
    ListeningStartedEvent,
    ListeningStoppedEvent,
    NoSpeechEvent,
    RouteEvent,
    ToolResultEvent,
    TranscriptEvent,
)
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant, State
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry

logger = logging.getLogger("voicecore")


def setup_cli_event_logger(bus: EventBus) -> None:
    """Print structured events to stdout for CLI visibility."""
    def on_event(e: Event) -> None:
        if isinstance(e, ListeningStartedEvent):
            print("\n[EVENT:LISTENING_STARTED] Recording speech buffer...")
        elif isinstance(e, ListeningStoppedEvent):
            print("[EVENT:LISTENING_STOPPED] Audio capture complete.")
        elif isinstance(e, TranscriptEvent):
            print(f"[EVENT:TRANSCRIPT] text=\"{e.text}\" language={e.language} asr_ms={e.asr_ms:.1f}ms")
        elif isinstance(e, RouteEvent):
            print(f"[EVENT:ROUTE] calls={e.calls} confidence={e.confidence:.4f} nlu_ms={e.nlu_ms:.1f}ms")
            if e.negation:
                print(f"             negation={e.negation}")
            if e.ungrounded:
                print(f"             ungrounded={e.ungrounded}")
        elif isinstance(e, GateEvent):
            print(f"[EVENT:GATE] decision={e.decision} reason='{e.reason}' call={e.call.get('name')}")
        elif isinstance(e, ConfirmRequestEvent):
            print(f"[EVENT:CONFIRM_REQUEST] call={e.call}")
        elif isinstance(e, ToolResultEvent):
            print(f"[EVENT:TOOL_RESULT] call={e.call.get('name')} ok={e.result.get('ok')} exec_ms={e.ms:.1f}ms")
        elif isinstance(e, NoSpeechEvent):
            print("[EVENT:NO_SPEECH] Empty transcript / silence detected (returning to IDLE)")
        elif isinstance(e, ErrorEvent):
            print(f"[EVENT:ERROR] stage={e.stage} error={e.error_type}: {e.message}")
        elif isinstance(e, DoneEvent):
            print(f"[EVENT:DONE] total_pipeline_ms={e.total_ms:.1f}ms")

    bus.subscribe_all(on_event)


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceCore: Offline voice layer for Windows")
    parser.add_argument("--text", type=str, help="Run pipeline with raw text input (no microphone)")
    parser.add_argument("--mic", action="store_true", help="Run push-to-talk microphone mode")
    parser.add_argument("--config", type=str, default="config/voicecore.toml", help="Path to voicecore.toml config")
    parser.add_argument("--dry-run", action="store_true", help="Simulate tool actions without OS side-effects")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="[DEV-ONLY] Automatically approve confirmation prompts for T0/T1; never applies to T2",
    )
    parser.add_argument("--no-log", action="store_true", help="Disable structured event console output")

    args = parser.parse_args()

    if not args.text and not args.mic:
        parser.print_help()
        print("\nSpecify --text \"<utterance>\" or --mic to run VoiceCore.")
        return 0

    # 1. Locate and load configuration
    config_path = Path(args.config)
    if not config_path.is_file():
        candidate = Path("voicecore") / args.config
        if candidate.is_file():
            config_path = candidate
        else:
            config_path = Path(__file__).resolve().parent.parent.parent / "config" / "voicecore.toml"

    config = VoiceCoreConfig.from_toml(config_path) if config_path.is_file() else VoiceCoreConfig()

    # 2. Tool Registry
    registry = ToolRegistry()

    if args.dry_run:
        def open_app_dry(app_name: str) -> dict:
            """Open an application by name, for example notepad, calculator, chrome."""
            return open_app(app_name, dry_run=True)
        open_app_dry.__name__ = "open_app"
        registry.register(open_app_dry, tier="T1", name="open_app")
    else:
        registry.register(open_app, tier="T1", name="open_app")

    # 3. Policy Gate & EventBus
    gate = PolicyGate(config=config.policy, registry=registry)
    event_bus = EventBus()

    if not args.no_log:
        setup_cli_event_logger(event_bus)

    # 4. Router & ASR
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

    def cli_confirmer(call) -> bool:
        tier = registry.get_tier(call.name)
        if tier == "T2":
            print(f"[SECURITY] Action '{call.name}' is Tier T2 (privileged/destructive). Auto-confirm (--yes) is disabled.")
            return False

        if args.yes or args.dry_run:
            print(f"[CLI] Auto-confirming action '{call.name}' (Tier {tier})")
            return True
        try:
            resp = input(f"Confirm execution of '{call.name}' with arguments {call.arguments}? [y/N]: ")
            return resp.strip().lower() in ("y", "yes")
        except EOFError:
            return False

    # Text mode execution
    if args.text:
        print(f"\nVoiceCore running text utterance: \"{args.text}\"")
        results = assistant.run_text(args.text, confirmer=cli_confirmer)
        print("\nPipeline Result Summary:")
        for res in results:
            print(f"  - Call: {res.get('call', {}).get('name')}({res.get('call', {}).get('arguments')})")
            print(f"    Status: {res.get('status')}")
            if "result" in res:
                print(f"    Output: {res.get('result')}")
            if "reason" in res:
                print(f"    Reason: {res.get('reason')}")
        return 0

    # Mic Push-to-Talk execution
    if args.mic:
        audio_capture = AudioCapture(config=config.audio)
        print("\n" + "=" * 60)
        print(" VoiceCore Push-to-Talk Activated")
        print(f" - Hotkey: {config.audio.hotkey}")
        print(f" - Input Device: [{audio_capture.device_index}] {audio_capture.device_name}")
        print(f" - Native Sample Rate: {audio_capture.native_rate} Hz (Resampled to 16 kHz via soxr)")
        print(f" - Min Press Threshold: {config.audio.min_press_seconds}s (ignores short taps)")
        print(f" - Max Duration Cap: {config.audio.max_seconds}s")
        print(" Hold hotkey to speak, release to execute. Press Ctrl+C to exit.")
        print("=" * 60)

        press_time = 0.0

        def on_press():
            nonlocal press_time
            # Barge-in protection: ignore press if assistant is busy
            if assistant.state != State.IDLE:
                return

            assistant.state = State.LISTENING
            press_time = time.monotonic()
            event_bus.publish(ListeningStartedEvent(run_id="mic_capture"))
            try:
                audio_capture.start_capture()
            except Exception as e:
                print(f"[AUDIO ERROR] {e}")
                assistant.state = State.IDLE

        def on_release():
            nonlocal press_time
            if assistant.state != State.LISTENING:
                return

            duration = time.monotonic() - press_time
            audio = audio_capture.stop_capture()
            event_bus.publish(ListeningStoppedEvent(run_id="mic_capture"))

            if duration < config.audio.min_press_seconds:
                print(f"[AUDIO] Ignored short press ({duration:.2f}s < {config.audio.min_press_seconds}s)")
                assistant.state = State.IDLE
                return

            print(f"[AUDIO] Captured {duration:.2f}s of audio ({len(audio)} samples at 16kHz). Processing...")

            # Run pipeline in a background worker thread so the hotkey listener never blocks
            def worker():
                try:
                    res = assistant.run_audio(audio, confirmer=cli_confirmer)
                    print("\nResult Summary:")
                    for r in res:
                        print(f"  - Action: {r.get('call', {}).get('name')}({r.get('call', {}).get('arguments')}) -> {r.get('status')}")
                except Exception as ex:
                    print(f"[PIPELINE ERROR] {ex}")

            threading.Thread(target=worker, daemon=True).start()

        listener = HotkeyListener(
            combo_str=config.audio.hotkey,
            on_press=on_press,
            on_release=on_release,
        )

        listener.start()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nShutting down VoiceCore push-to-talk...")
        finally:
            listener.stop()
            audio_capture.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
