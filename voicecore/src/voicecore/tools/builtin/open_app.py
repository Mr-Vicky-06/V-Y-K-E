"""Open application tool (T1) with strict allowlist containment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

DEFAULT_ALLOWLIST = {
    "notepad": "notepad.exe",
    "node pad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
}


def find_default_allowlist_file() -> Optional[Path]:
    """Find apps.allowlist.json in standard config directories."""
    candidates = [
        Path("config/apps.allowlist.json"),
        Path("voicecore/config/apps.allowlist.json"),
        Path(__file__).resolve().parent.parent.parent.parent / "config" / "apps.allowlist.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_allowlist(allowlist_path: Optional[str | Path] = None) -> Dict[str, str]:
    """Load authorized app mapping from JSON file or return built-in defaults."""
    target_path = Path(allowlist_path) if allowlist_path else find_default_allowlist_file()
    if target_path and target_path.is_file():
        try:
            with target_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {k.lower().strip(): str(v).strip() for k, v in data.items()}
        except Exception:
            pass
    return DEFAULT_ALLOWLIST.copy()


def open_app(
    app_name: str,
    allowlist: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Open an application by name, for example notepad, calculator, chrome."""
    if not app_name or not isinstance(app_name, str):
        return {"ok": False, "error": "invalid_app_name", "message": "App name must be a non-empty string."}

    # Normalize input: trim and lowercase
    normalized = app_name.lower().strip()
    mapping = allowlist if allowlist is not None else load_allowlist()

    # Security rule 1: Arbitrary text never reaches execution; must strictly match allowlist key
    if normalized not in mapping:
        return {
            "ok": False,
            "error": "not_allowed",
            "message": f"'{app_name}' is not an allowed app.",
        }

    # Security rule 2: Executable is retrieved exclusively from allowlist dictionary value
    executable = mapping[normalized]

    if dry_run:
        return {
            "ok": True,
            "app_name": normalized,
            "executable": executable,
            "dry_run": True,
        }

    # Security rule 3: subprocess.Popen is called with an argument vector, NEVER shell=True
    try:
        subprocess.Popen([executable], shell=False)
        return {
            "ok": True,
            "app_name": normalized,
            "executable": executable,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": "launch_failed",
            "message": f"Failed to launch '{executable}': {e}",
        }


def open_app_precheck(args: Dict[str, Any], allowlist: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
    """Pre-check for open_app: argument app_name must resolve in the allowlist."""
    app_name = args.get("app_name")
    if not app_name or not isinstance(app_name, str) or not app_name.strip():
        return False, "App name must be a non-empty string."

    normalized = app_name.lower().strip()
    mapping = allowlist if allowlist is not None else load_allowlist()
    if normalized not in mapping:
        return False, f"'{app_name}' is not an allowed app."
    return True, ""
