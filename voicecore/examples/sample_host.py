"""Sample host integration showcasing VoiceCore Level 1 Python plugin usage."""
from __future__ import annotations

from voicecore import VoiceAssistant, tool


# 1. Define a host tool with explicit tier and precheck (eligible to ACT directly on high confidence)
def check_minutes(args: dict) -> tuple[bool, str]:
    mins = args.get("minutes", 0)
    if mins <= 0 or mins > 180:
        return False, f"Focus minutes must be between 1 and 180 (got {mins})"
    return True, "Valid duration"


@tool(tier="T1", precheck=check_minutes, triggers=["focus", "focus session", "deep work"])
def start_focus_session(minutes: int = 25) -> dict:
    """Start a focus work session for a given number of minutes."""
    print(f"[Host Action] Focus mode activated for {minutes} minutes! Do not disturb.")
    return {"status": "started", "minutes": minutes}


# 2. Define a host tool without precheck (will default to always-CONFIRM for safety)
@tool(tier="T1", triggers=["mute", "silence", "quiet"])
def silence_notifications() -> dict:
    """Silence all computer notifications."""
    print("[Host Action] Notifications silenced.")
    return {"status": "silenced"}


def main() -> None:
    # Initialize assistant from configuration
    va = VoiceAssistant.from_config("config/voicecore.toml", load_builtins=True)

    # Register host tools
    va.register(start_focus_session)
    va.register(silence_notifications)

    # Subscribe to life-cycle events
    va.on("transcript", lambda e: print(f"[Event: Transcript] '{e.text}' (took {e.asr_ms:.1f}ms)"))
    va.on("gate", lambda e: print(f"[Event: Gate] Decision={e.decision} ({e.reason})"))
    va.on(
        "confirm_request",
        lambda e: (
            print(f"[Event: Confirmation Required] Confirming {e.call['name']}? Responding True."),
            e.respond(True),
        ),
    )
    va.on("tool_result", lambda e: print(f"[Event: Tool Result] {e.result} (took {e.ms:.1f}ms)"))

    print("--- 1. Testing compliant host tool (start_focus_session) ---")
    va.run_text("start a focus session for 30 minutes")

    print("\n--- 2. Testing un-prechecked host tool (silence_notifications: always-CONFIRM) ---")
    va.run_text("silence notifications")


if __name__ == "__main__":
    main()

