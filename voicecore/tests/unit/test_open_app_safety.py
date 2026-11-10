from unittest.mock import patch
import pytest

from voicecore.tools.builtin.open_app import open_app, load_allowlist


def test_open_app_aliases():
    """Verify both calculator and its alias calc resolve correctly."""
    res1 = open_app("calculator", dry_run=True)
    res2 = open_app("calc", dry_run=True)

    assert res1["ok"] is True
    assert res1["executable"] == "calc.exe"

    assert res2["ok"] is True
    assert res2["executable"] == "calc.exe"


def test_open_app_not_allowlisted_refused():
    """Verify non-allowlisted apps are refused with not_allowed."""
    unauthorized = ["powershell", "cmd", "bash", "regedit", "format", "random_malware"]
    for app in unauthorized:
        res = open_app(app, dry_run=True)
        assert res["ok"] is False
        assert res["error"] == "not_allowed"


def test_open_app_injection_attempts_refused():
    """Verify injection payloads are never executed and rejected by allowlist."""
    payloads = [
        "notepad & calc",
        "calc.exe; dir",
        "notepad | whoami",
        "calc && rm -rf",
        "notepad\ncalc",
        "powershell.exe -Command Write-Host evil",
    ]
    for p in payloads:
        res = open_app(p, dry_run=True)
        assert res["ok"] is False
        assert res["error"] == "not_allowed"


def test_open_app_subprocess_args_and_no_shell():
    """Verify subprocess.Popen is invoked with exact executable vector and shell=False."""
    with patch("subprocess.Popen") as mock_popen:
        res = open_app("notepad", dry_run=False)
        assert res["ok"] is True
        mock_popen.assert_called_once_with(["notepad.exe"], shell=False)


def test_open_app_invalid_inputs():
    """Verify non-string or empty inputs are rejected safely."""
    assert open_app("", dry_run=True)["ok"] is False
    assert open_app(None, dry_run=True)["ok"] is False
    assert open_app(123, dry_run=True)["ok"] is False
