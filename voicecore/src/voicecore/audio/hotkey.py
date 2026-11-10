"""Selective push-to-talk hotkey listener using pynput."""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Set

from pynput import keyboard

logger = logging.getLogger(__name__)


def normalize_hotkey_string(combo_str: str) -> str:
    """Normalize combo strings like 'ctrl+alt+space' into pynput format '<ctrl>+<alt>+<space>'."""
    special_names = {
        "ctrl", "control", "alt", "shift", "space", "cmd", "super", "win",
        "enter", "tab", "esc", "escape", "backspace", "delete", "up", "down", "left", "right"
    }
    parts = [p.strip().lower() for p in combo_str.split("+") if p.strip()]
    normalized = []
    for p in parts:
        if p.startswith("<") and p.endswith(">"):
            normalized.append(p)
        elif p in special_names:
            normalized.append(f"<{p}>")
        else:
            normalized.append(p)
    return "+".join(normalized)


class HotkeyListener:
    """Listens exclusively for a configured hotkey combination.
    
    Security & Privacy:
    - Never stores, logs, or tracks non-combo keystrokes.
    - Activates only on full combo press; deactivates on any combo key release.
    """

    def __init__(
        self,
        combo_str: str = "ctrl+alt+space",
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ) -> None:
        self.combo_str = combo_str
        self.on_press_cb = on_press
        self.on_release_cb = on_release

        pynput_combo = normalize_hotkey_string(combo_str)
        self._parsed_keys = set(keyboard.HotKey.parse(pynput_combo))

        self._lock = threading.Lock()
        self._active_keys: Set[Any] = set()
        self._is_active = False
        self._listener: Optional[keyboard.Listener] = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._is_active

    def _canonical(self, key: Any) -> Any:
        if self._listener is not None:
            return self._listener.canonical(key)
        return key

    def _on_key_press(self, key: Any) -> None:
        canonical_key = self._canonical(key)
        # Security: Immediately discard any key not in our configured combo
        if canonical_key not in self._parsed_keys:
            return

        with self._lock:
            self._active_keys.add(canonical_key)
            if self._parsed_keys.issubset(self._active_keys) and not self._is_active:
                self._is_active = True
                if self.on_press_cb:
                    try:
                        self.on_press_cb()
                    except Exception as e:
                        logger.error("Error in hotkey on_press callback: %s", e)

    def _on_key_release(self, key: Any) -> None:
        canonical_key = self._canonical(key)
        if canonical_key not in self._parsed_keys:
            return

        with self._lock:
            if canonical_key in self._active_keys:
                self._active_keys.remove(canonical_key)

            if self._is_active:
                self._is_active = False
                if self.on_release_cb:
                    try:
                        self.on_release_cb()
                    except Exception as e:
                        logger.error("Error in hotkey on_release callback: %s", e)

    def start(self) -> None:
        """Start global keyboard hook in background thread."""
        with self._lock:
            if self._listener is not None:
                return

            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.daemon = True
            self._listener.start()

    def stop(self) -> None:
        """Stop keyboard hook."""
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None
            self._active_keys.clear()
            self._is_active = False

    def __enter__(self) -> HotkeyListener:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

