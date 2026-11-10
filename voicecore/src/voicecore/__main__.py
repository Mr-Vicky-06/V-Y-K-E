"""VoiceCore CLI entrypoint.

Supports:
    python -m voicecore --text "open notepad"
    python -m voicecore --text "open notepad" --dry-run
    python -m voicecore --text "open notepad" --yes
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from voicecore.config import VoiceCoreConfig
from voicecore.events import (
    ConfirmRequestEvent,
    DoneEvent,
    ErrorEvent,
    Event,
    EventBus,
    GateEvent,
    NoSpeechEvent,
    RouteEvent,
    ToolResultEvent,
)
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry


def setup_cli_event_logger(bus: EventBus) -> None:
    """Print structured events to stdout for CLI visibility."""
    def on_event(e: Event) -> None:
        if isinstance(e, RouteEvent):
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
            print("[EVENT:NO_SPEECH] Empty input detected")
        elif isinstance(e, ErrorEvent):
            print(f"[EVENT:ERROR] stage={e.stage} error={e.error_type}: {e.message}")
        elif isinstance(e, DoneEvent):
            print(f"[EVENT:DONE] total_pipeline_ms={e.total_ms:.1f}ms")

    bus.subscribe_all(on_event)


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceCore: Offline voice layer for Windows")
    parser.add_argument("--text", type=str, help="Run pipeline with raw text input (no microphone)")
    parser.add_argument("--config", type=str, default="config/voicecore.toml", help="Path to voicecore.toml config")
    parser.add_argument("--dry-run", action="store_true", help="Simulate tool actions without OS side-effects")
    parser.add_argument("--yes", "-y", action="store_true", help="Automatically confirm actions that require confirmation")
    parser.add_argument("--no-log", action="store_true", help="Disable structured event console output")

    args = parser.parse_args()

    if not args.text:
        parser.print_help()
        print("\nNote: Microphone mode (--mic) is implemented in Milestone M2.")
        return 0

    # 1. Locate and load configuration
    config_path = Path(args.config)
    if not config_path.is_file():
        # Check relative to parent or voicecore package root
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

    # 4. Router & Assistant
    router = NeedleRouter(registry=registry, stateless=True)
    assistant = Assistant(
        router=router,
        registry=registry,
        policy_gate=gate,
        config=config,
        event_bus=event_bus,
    )

    def cli_confirmer(call) -> bool:
        if args.yes or args.dry_run:
            print(f"[CLI] Auto-confirming action '{call.name}'")
            return True
        try:
            resp = input(f"Confirm execution of '{call.name}' with arguments {call.arguments}? [y/N]: ")
            return resp.strip().lower() in ("y", "yes")
        except EOFError:
            return False

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


if __name__ == "__main__":
    sys.exit(main())
