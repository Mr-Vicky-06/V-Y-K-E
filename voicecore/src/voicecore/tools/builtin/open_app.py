"""Open application tool (T1)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

DEFAULT_ALLOWLIST = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
}


def load_allowlist(allowlist_path: Optional[str | Path] = None) -> Dict[str, str]:
    """Load authorized app mapping from JSON file or return default."""
    if allowlist_path:
        p = Path(allowlist_path)
        if p.is_file():
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {k.lower().strip(): v for k, v in data.items()}
            except Exception:
                pass
    return DEFAULT_ALLOWLIST.copy()


def open_app(app_name: str, allowlist: Optional[Dict[str, str]] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Open an application by name, for example notepad, calculator, chrome."""
    if not app_name or not isinstance(app_name, str):
        return {"ok": False, "error": "invalid_app_name"}

    normalized = app_name.lower().strip()
    mapping = allowlist if allowlist is not None else load_allowlist()

    if normalized not in mapping:
        return {
            "ok": False,
            "error": "not_allowed",
            "message": f"Application '{app_name}' is not in the authorized allowlist.",
        }

    executable = mapping[normalized]

    if dry_run:
        return {
            "ok": True,
            "app_name": normalized,
            "executable": executable,
            "dry_run": True,
        }

    # Launch without shell=True per security rule
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
