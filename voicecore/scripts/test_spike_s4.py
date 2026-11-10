import inspect
import pynput
from pynput import keyboard

print("=== pynput inspect ===")
print("pynput version:", getattr(pynput, "__version__", "unknown"))
print("keyboard members:", [m for m in dir(keyboard) if not m.startswith("_")])

# Inspect GlobalHotKeys
print("\nGlobalHotKeys signature:", inspect.signature(keyboard.GlobalHotKeys))
print("HotKey signature:", inspect.signature(keyboard.HotKey))

# Test parsing hotkey
parsed = keyboard.HotKey.parse("<ctrl>+<alt>+<space>")
print("Parsed <ctrl>+<alt>+<space>:", parsed)

# Test press/release state tracking pattern for push-to-talk
class PushToTalkListener:
    """Detects hold and release of configured hotkey without storing any other keystrokes.
    
    Security: No keystroke logs, no buffers of non-hotkey characters.
    """
    def __init__(self, combo_str="<ctrl>+<alt>+<space>", on_press=None, on_release=None):
        self.hotkey = keyboard.HotKey(keyboard.HotKey.parse(combo_str), self._on_activate)
        self.on_press_cb = on_press
        self.on_release_cb = on_release
        self.is_active = False

    def _on_activate(self):
        if not self.is_active:
            self.is_active = True
            if self.on_press_cb:
                self.on_press_cb()

    def on_key_press(self, key):
        # HotKey object tracks state internally for configured keys only
        self.hotkey.press(self.listener.canonical(key))

    def on_key_release(self, key):
        self.hotkey.release(self.listener.canonical(key))
        # If any key of the combo was released while active, deactivate
        canonical_key = self.listener.canonical(key)
        if self.is_active and canonical_key in self.hotkey._keys:
            self.is_active = False
            if self.on_release_cb:
                self.on_release_cb()

# Instantiate to verify construction
ptt = PushToTalkListener()
print("\nPushToTalkListener constructed successfully. Hotkey keys tracked count:", len(ptt.hotkey._keys))

