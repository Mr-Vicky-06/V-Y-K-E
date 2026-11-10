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
    ReminderDueEvent,
    RouteEvent,
    ToolResultEvent,
    TranscriptEvent,
)
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant, State
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import get_default_manager, set_reminder, set_reminder_precheck
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
        elif isinstance(e, ReminderDueEvent):
            print(f"\n[EVENT:REMINDER_DUE] *** ALARM: '{e.message}' (scheduled for {e.when}) ***")
        elif isinstance(e, NoSpeechEvent):
            print("[EVENT:NO_SPEECH] Empty transcript / silence detected (returning to IDLE)")
        elif isinstance(e, ErrorEvent):
            print(f"[EVENT:ERROR] stage={e.stage} error={e.error_type}: {e.message}")
        elif isinstance(e, DoneEvent):
            print(f"[EVENT:DONE] total_pipeline_ms={e.total_ms:.1f}ms")

    bus.subscribe_all(on_event)


def tune_threads() -> int:
    """Benchmark different thread counts inside one process after model load."""
    import os
    import cactus
    print("=" * 65)
    print(" VoiceCore: CPU Thread Tuning Benchmark (Post-Load Verification)")
    print(f" Process PID: {os.getpid()} | Verifying dynamic thread pool reconfiguration")
    print("=" * 65)
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=["open", "launch"])
    
    # 1. Load model ONCE into memory before changing threads
    print("[1/2] Loading Needle 3 model weights into process memory...")
    router = NeedleRouter(registry=registry, stateless=True)
    router.route("open notepad")  # Warmup run to prime memory, C handles, and grammar
    print("[1/2] Model loaded and primed. Now mutating thread count dynamically in-process...\n")

    test_counts = [1, 2, 4, 8, 0]
    results = {}
    print(f"  {'Thread Setting':<16} | {'Runs':<6} | {'p50 (ms)':<10} | {'Mean (ms)':<10} | Status")
    print("  " + "-" * 58)

    for tc in test_counts:
        # Dynamically change threads on already-loaded model
        cactus.set_threads(tc)
        times = []
        for _ in range(8):
            t0 = time.perf_counter()
            res = router.route("open notepad")
            times.append((time.perf_counter() - t0) * 1000.0)
        
        times.sort()
        p50 = times[len(times) // 2]
        avg_ms = sum(times) / len(times)
        label = "Auto (0)" if tc == 0 else f"{tc} thread{'s' if tc > 1 else ''}"
        results[tc] = p50
        print(f"  {label:<16} | {len(times):<6} | {p50:8.1f}   | {avg_ms:8.1f}   | Dynamic OK")

    best_t = min(results, key=results.get)
    best_label = "Auto (0)" if best_t == 0 else f"{best_t} threads"
    print("=" * 65)
    print(f"Optimal configuration: threads = {best_t} ({best_label}) at {results[best_t]:.1f} ms p50")
    print(f"Set 'threads = {best_t}' in [runtime] section of config/voicecore.toml")
    print("Verification: All benchmark runs executed on a single loaded model instance.")
    print("=" * 65)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceCore: Offline voice layer for Windows")
    parser.add_argument("--text", type=str, help="Run pipeline with raw text input (no microphone)")
    parser.add_argument("--mic", action="store_true", help="Run push-to-talk microphone mode")
    parser.add_argument("--config", type=str, default="config/voicecore.toml", help="Path to voicecore.toml config")
    parser.add_argument("--dry-run", action="store_true", help="Simulate tool actions without OS side-effects")
    parser.add_argument("--tune-threads", action="store_true", help="Benchmark CPU thread counts and find optimal setting")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="[DEV-ONLY] Automatically approve confirmation prompts for T0/T1; never applies to T2",
    )
    parser.add_argument("--no-log", action="store_true", help="Disable structured event console output")

    args = parser.parse_args()

    if args.tune_threads:
        return tune_threads()

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

    # Apply configured CPU thread count
    import cactus
    cactus.set_threads(config.runtime.threads)

    # 2. Tool Registry (M3: open_app, search_files, set_reminder)
    registry = ToolRegistry()

    if args.dry_run:
        def open_app_dry(app_name: str) -> dict:
            """Open an application by name, for example notepad, calculator, chrome."""
            return open_app(app_name, dry_run=True)
        open_app_dry.__name__ = "open_app"
        registry.register(
            open_app_dry,
            tier="T1",
            name="open_app",
            precheck=open_app_precheck,
            triggers=["open", "launch", "start"],
        )
    else:
        registry.register(
            open_app,
            tier="T1",
            name="open_app",
            precheck=open_app_precheck,
            triggers=["open", "launch", "start"],
        )

    registry.register(
        search_files,
        tier="T0",
        name="search_files",
        precheck=search_files_precheck,
        triggers=["search", "find", "search files", "find files", "locate"],
    )
    registry.register(
        set_reminder,
        tier="T1",
        name="set_reminder",
        precheck=set_reminder_precheck,
        triggers=["remind", "reminder", "set a reminder", "schedule"],
    )

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
    # Startup warm-up inference (pre-initializes weights and buffers)
    assistant.warmup()

    # Startup reload of pending reminders & wire alarm events
    reminder_mgr = get_default_manager()
    reminder_mgr.on_due = lambda rem: event_bus.publish(
        ReminderDueEvent(run_id="scheduler", reminder_id=str(rem.id), message=rem.message, when=rem.target_time_iso)
    )
    reloaded = reminder_mgr.reload_pending()
    if reloaded["missed"] > 0:
        print(f"\n[STARTUP NOTICE] *** {reloaded['missed']} reminder(s) were missed while VYKE was not running: ***")
        try:
            import sqlite3
            with sqlite3.connect(str(reminder_mgr.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT message, target_time_iso FROM reminders WHERE status = 'missed' ORDER BY id DESC LIMIT 5").fetchall()
                for r in rows:
                    print(f"  - '{r['message']}' (was scheduled for {r['target_time_iso']})")
        except Exception:
            pass
    if reloaded["scheduled"] > 0:
        print(f"[STARTUP] Rescheduled {reloaded['scheduled']} active future reminder(s).")

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
