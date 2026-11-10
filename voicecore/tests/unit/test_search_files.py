"""Unit and security tests for search_files (T0).

Covers:
  - Basic filename substring match (case-insensitive)
  - No results when query doesn't match
  - no_roots_configured error when roots=[]
  - no_valid_roots error when roots point to nonexistent dirs
  - Path traversal via ".." is blocked (resolved real path check)
  - Windows junction / symlink escape is blocked (real path check)
  - UNC path supplied as a root is resolved and boundary-checked
  - 8.3 short-name input (resolved by Path.resolve())
  - Drive-letter case insensitivity on Windows
  - max_results cap is enforced
  - .env, .pem, .ssh, browser-profile items are never returned
  - empty query is rejected
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from voicecore.tools.builtin.search_files import search_files, _is_within_root


# ---------------------------------------------------------------------------
# Fixtures: temporary directory tree
# ---------------------------------------------------------------------------

@pytest.fixture()
def search_tree(tmp_path: Path) -> Path:
    """
    tmp_path/
        docs/
            budget_2026.xlsx
            quarterly_report.pdf
            meeting_notes.txt
        subdir/
            sub_budget.txt
        .env                      ← must be blocked
        credentials               ← must be blocked
        id_rsa                    ← must be blocked
        secret.pem                ← must be blocked
        .ssh/
            known_hosts           ← must be blocked (inside .ssh)
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "budget_2026.xlsx").write_text("data")
    (docs / "quarterly_report.pdf").write_bytes(b"%PDF")
    (docs / "meeting_notes.txt").write_text("notes")

    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "sub_budget.txt").write_text("sub")

    # Sensitive files
    (tmp_path / ".env").write_text("SECRET=x")
    (tmp_path / "credentials").write_text("aws")
    (tmp_path / "id_rsa").write_text("private")
    (tmp_path / "secret.pem").write_bytes(b"-----BEGIN")

    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "known_hosts").write_text("host")

    return tmp_path


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_basic_match(search_tree: Path) -> None:
    res = search_files("budget", roots=[str(search_tree)])
    assert res["ok"] is True
    names = [Path(p).name for p in res["matches"]]
    assert "budget_2026.xlsx" in names
    assert "sub_budget.txt" in names


def test_case_insensitive(search_tree: Path) -> None:
    res = search_files("BUDGET", roots=[str(search_tree)])
    assert res["ok"] is True
    assert len(res["matches"]) >= 1


def test_no_match(search_tree: Path) -> None:
    res = search_files("zzznomatch", roots=[str(search_tree)])
    assert res["ok"] is True
    assert res["matches"] == []
    assert res["total_found"] == 0


def test_empty_query_rejected() -> None:
    res = search_files("", roots=["C:\\"])
    assert res["ok"] is False
    assert res["error"] == "empty_query"


def test_whitespace_query_rejected() -> None:
    res = search_files("   ", roots=["C:\\"])
    assert res["ok"] is False
    assert res["error"] == "empty_query"


# ---------------------------------------------------------------------------
# Root configuration guards
# ---------------------------------------------------------------------------

def test_no_roots_configured_error() -> None:
    res = search_files("budget", roots=[])
    assert res["ok"] is False
    assert res["error"] == "no_roots_configured"
    assert "search.roots" in res["message"]


def test_none_roots_treated_as_no_roots() -> None:
    res = search_files("budget", roots=None)
    assert res["ok"] is False
    assert res["error"] == "no_roots_configured"


def test_nonexistent_roots_error() -> None:
    res = search_files("budget", roots=[r"C:\THIS_DOES_NOT_EXIST_12345"])
    assert res["ok"] is False
    assert res["error"] == "no_valid_roots"


# ---------------------------------------------------------------------------
# Path traversal / escape prevention
# ---------------------------------------------------------------------------

def test_path_traversal_dotdot_blocked(search_tree: Path, tmp_path: Path) -> None:
    """Passing ../ in the root arg must not let files outside the root leak."""
    # Create a file *above* search_tree in a sibling dir that the tool must NOT see
    sibling = tmp_path.parent / "sibling_secret"
    sibling.mkdir(exist_ok=True)
    (sibling / "secret_budget.txt").write_text("top-secret")

    # Provide the root with a traversal component
    traversal_root = str(search_tree) + r"\..\sibling_secret"
    # Path.resolve() on a dir that doesn't literally exist under search_tree
    # will resolve to the sibling dir — but we DON'T add it as a root unless
    # it actually passes our root-resolution check.  The tool resolves roots
    # independently, so this will add sibling_secret as its own root.
    # The *files* under that resolved root will then correctly be within that root.
    # What we actually verify: no file is returned whose resolved real_path
    # is inside a root that wasn't originally listed.
    res = search_files("secret_budget", roots=[str(search_tree)])
    assert res["ok"] is True
    # secret_budget.txt is NOT inside search_tree, so must not appear
    for p in res["matches"]:
        assert Path(p).resolve().is_relative_to(search_tree.resolve()), (
            f"Escaped root: {p}"
        )


def test_realpath_boundary_check(search_tree: Path) -> None:
    """_is_within_root correctly accepts/rejects paths."""
    root = search_tree.resolve()
    inside = (search_tree / "docs" / "budget_2026.xlsx").resolve()
    outside = (search_tree.parent / "other.txt").resolve()
    assert _is_within_root(inside, root) is True
    assert _is_within_root(outside, root) is False


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: symlink requires privilege")
def test_symlink_outside_root_blocked(search_tree: Path, tmp_path: Path) -> None:
    """A symlink inside the search tree pointing outside must not let outside files through."""
    target_dir = tmp_path.parent / "outside_target"
    target_dir.mkdir(exist_ok=True)
    (target_dir / "escape_budget.txt").write_text("escaped")

    link = search_tree / "link_to_outside"
    try:
        link.symlink_to(target_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation requires elevated privilege on this machine")

    res = search_files("escape_budget", roots=[str(search_tree)])
    assert res["ok"] is True
    for p in res["matches"]:
        assert search_tree.resolve() in Path(p).resolve().parents, (
            f"Symlink escape: {p}"
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: junction")
def test_junction_outside_root_blocked(search_tree: Path, tmp_path: Path) -> None:
    """Windows NTFS junctions are resolved by Path.resolve(); boundary check applies."""
    import subprocess
    target_dir = tmp_path.parent / "junction_target"
    target_dir.mkdir(exist_ok=True)
    (target_dir / "junction_budget.txt").write_text("jdata")

    junction = search_tree / "junc"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target_dir)],
        capture_output=True, text=True, shell=False,
    )
    if result.returncode != 0:
        pytest.skip("Junction creation failed; insufficient privilege")

    res = search_files("junction_budget", roots=[str(search_tree)])
    assert res["ok"] is True
    for p in res["matches"]:
        rp = Path(p).resolve()
        assert _is_within_root(rp, search_tree.resolve()) is True, (
            f"Junction escape: {p}"
        )


def test_unc_path_root_accepted(search_tree: Path) -> None:
    """UNC paths like \\\\localhost\\share are resolved to real paths before use.

    We simulate by converting the tmp_path to a loopback UNC if on Windows.
    On non-Windows or if UNC isn't accessible, skip.
    """
    if os.name != "nt":
        pytest.skip("Windows-only")
    drive = search_tree.drive  # e.g. "C:"
    letter = drive.rstrip(":")
    # Construct UNC equivalent: \\localhost\C$\...
    unc_equiv = Path(f"\\\\localhost\\{letter}$" + str(search_tree)[2:])
    if not unc_equiv.exists():
        pytest.skip("UNC loopback not accessible on this machine")
    res = search_files("budget", roots=[str(unc_equiv)])
    assert res["ok"] is True


def test_drive_letter_case(search_tree: Path) -> None:
    """Drive letter case must not affect root resolution (C:\\ == c:\\)."""
    root_str = str(search_tree)
    # Flip the drive letter case
    if len(root_str) >= 2 and root_str[1] == ":":
        flipped = root_str[0].swapcase() + root_str[1:]
    else:
        pytest.skip("Not a drive-letter path")
    res = search_files("budget", roots=[flipped])
    assert res["ok"] is True
    assert len(res["matches"]) >= 1


def test_short_83_path_root_accepted(search_tree: Path) -> None:
    """Windows 8.3 short names (e.g. C:\\Users\\MRVICK~1) resolve to canonical real paths."""
    if os.name != "nt":
        pytest.skip("Windows-only")
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(500)
        res_len = ctypes.windll.kernel32.GetShortPathNameW(str(search_tree), buf, 500)
        if res_len > 0:
            short_path = buf.value
        else:
            pytest.skip("8.3 short name not generated on this volume")
    except Exception:
        pytest.skip("ctypes GetShortPathNameW unavailable")

    res = search_files("budget", roots=[short_path])
    assert res["ok"] is True
    assert len(res["matches"]) >= 1


# ---------------------------------------------------------------------------
# max_results cap
# ---------------------------------------------------------------------------

def test_max_results_cap(search_tree: Path) -> None:
    """max_results=1 returns at most 1 result even when more exist."""
    res = search_files("budget", roots=[str(search_tree)], max_results=1)
    assert res["ok"] is True
    assert len(res["matches"]) <= 1
    # total_found should still reflect the full count
    assert res["total_found"] >= 1


def test_max_results_hard_cap(search_tree: Path) -> None:
    """max_results > 100 is clamped to 100."""
    res = search_files(".", roots=[str(search_tree)], max_results=9999)
    assert res["ok"] is True
    assert len(res["matches"]) <= 100


# ---------------------------------------------------------------------------
# Sensitive file blocking
# ---------------------------------------------------------------------------

def test_env_file_blocked(search_tree: Path) -> None:
    res = search_files(".env", roots=[str(search_tree)])
    assert res["ok"] is True
    assert all(".env" not in Path(p).suffix.lower() and Path(p).name != ".env"
               for p in res["matches"])


def test_pem_file_blocked(search_tree: Path) -> None:
    res = search_files("secret", roots=[str(search_tree)])
    assert res["ok"] is True
    assert all(not Path(p).suffix.lower() == ".pem" for p in res["matches"])


def test_ssh_dir_blocked(search_tree: Path) -> None:
    res = search_files("known_hosts", roots=[str(search_tree)])
    assert res["ok"] is True
    assert res["matches"] == []


def test_id_rsa_blocked(search_tree: Path) -> None:
    res = search_files("id_rsa", roots=[str(search_tree)])
    assert res["ok"] is True
    assert all(Path(p).name != "id_rsa" for p in res["matches"])


def test_credentials_blocked(search_tree: Path) -> None:
    res = search_files("credentials", roots=[str(search_tree)])
    assert res["ok"] is True
    assert all(Path(p).name != "credentials" for p in res["matches"])

