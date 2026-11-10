from pynput import keyboard
from voicecore.audio.hotkey import HotkeyListener, normalize_hotkey_string


def test_normalize_hotkey_string():
    assert normalize_hotkey_string("ctrl+alt+space") == "<ctrl>+<alt>+<space>"
    assert normalize_hotkey_string("<ctrl>+<alt>+<space>") == "<ctrl>+<alt>+<space>"
    assert normalize_hotkey_string("ctrl+shift+a") == "<ctrl>+<shift>+a"


def test_hotkey_listener_combo_activation():
    presses = []
    releases = []

    listener = HotkeyListener(
        combo_str="ctrl+alt+space",
        on_press=lambda: presses.append(1),
        on_release=lambda: releases.append(1),
    )

    ctrl, alt, space = keyboard.HotKey.parse("<ctrl>+<alt>+<space>")
    other_key = keyboard.KeyCode.from_char("z")

    # Non-combo key has no effect
    listener._on_key_press(other_key)
    assert len(presses) == 0

    # Partial combo press
    listener._on_key_press(ctrl)
    listener._on_key_press(alt)
    assert len(presses) == 0
    assert listener.is_active is False

    # Full combo press triggers on_press
    listener._on_key_press(space)
    assert len(presses) == 1
    assert listener.is_active is True

    # Releasing any key of combo triggers on_release
    listener._on_key_release(space)
    assert len(releases) == 1
    assert listener.is_active is False


def test_hotkey_listener_ignores_unrelated_release():
    presses = []
    releases = []

    listener = HotkeyListener(
        combo_str="ctrl+alt+space",
        on_press=lambda: presses.append(1),
        on_release=lambda: releases.append(1),
    )

    other_key = keyboard.KeyCode.from_char("z")
    listener._on_key_release(other_key)
    assert len(releases) == 0


def test_hotkey_ignored_while_run_in_progress():
    """Verify that when assistant state is not IDLE, hotkey activation does not trigger capture."""
    from voicecore.runtime.assistant import State

    class MockAssistant:
        def __init__(self):
            self.state = State.EXECUTING  # Simulating active pipeline run

    assistant = MockAssistant()
    capture_started = []

    def on_press():
        if assistant.state != State.IDLE:
            return
        capture_started.append(True)

    listener = HotkeyListener(
        combo_str="ctrl+alt+space",
        on_press=on_press,
    )

    ctrl, alt, space = keyboard.HotKey.parse("<ctrl>+<alt>+<space>")
    listener._on_key_press(ctrl)
    listener._on_key_press(alt)
    listener._on_key_press(space)

    # Must be completely ignored because assistant.state != State.IDLE
    assert len(capture_started) == 0

    # Once assistant returns to IDLE, hotkey works
    assistant.state = State.IDLE
    listener._on_key_release(space)  # reset combo
    listener._on_key_press(space)
    assert len(capture_started) == 1

