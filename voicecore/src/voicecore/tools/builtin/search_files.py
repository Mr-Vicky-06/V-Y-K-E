"""search_files tool (T0) — filename-only substring search within configured roots.

P0 scope: searches file *names* only, not file contents.
The query is matched as a plain case-insensitive substring of the filename stem
plus extension (e.g. "budget" matches "Budget_2026.xlsx" and "q1-budget.pdf").

Security constraints
--------------------
* Only files whose *resolved* real path starts with one of the configured root
  directories are returned.  The check is applied *after* path resolution so
  that Windows junctions, symlinks, UNC paths and 8.3 short names cannot escape
  the boundary.
* .env files, .ssh directories, private-key files, and browser profile stores
  are always skipped, regardless of query.
* No symlinks are followed during traversal (rglob skips them on the read path;
  individual results are still realpath-checked).
* max_results caps the output list (default from config, hard cap 100).

Raises no exceptions to callers — all errors are returned as ok=False dicts.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Default Config Discovery
# ---------------------------------------------------------------------------

def find_default_config_file() -> Optional[Path]:
    """Find voicecore.toml in standard config directories."""
    candidates = [
        Path("config/voicecore.toml"),
        Path("voicecore/config/voicecore.toml"),
        Path(__file__).resolve().parent.parent.parent.parent / "config" / "voicecore.toml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_default_roots() -> List[str]:
    """Load search roots from voicecore.toml if configured."""
    cfg_file = find_default_config_file()
    if cfg_file and cfg_file.is_file():
        try:
            with cfg_file.open("rb") as f:
                data = tomllib.load(f)
                roots = data.get("search", {}).get("roots", [])
                if isinstance(roots, list):
                    return [str(r) for r in roots]
        except Exception:
            pass
    return []

# ---------------------------------------------------------------------------
# Blocked name patterns (security: skip unconditionally)
# ---------------------------------------------------------------------------

# Directory basenames that must never be entered
_BLOCKED_DIRS: frozenset[str] = frozenset({
    ".ssh",
    ".gnupg",
    ".aws",
    ".azure",
    ".gcloud",
    # Browser profile stores
    "default",          # Chrome / Edge default profile dir (inside User Data)
    "user data",        # Chrome / Edge
    "profiles.ini",     # Firefox (file, not dir, but guard anyway)
})

# File extensions / names that must never be returned
_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".env",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".ppk",
    ".asc",
    ".gpg",
    ".kdbx",   # KeePass database
    ".keystore",
    ".jks",
})

_BLOCKED_FILENAMES: frozenset[str] = frozenset({
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa.pub",
    "authorized_keys",
    "known_hosts",
    "credentials",      # AWS credentials file
    "config",           # guard: too broad; handled by dir check above for .ssh
})


def _is_blocked(path: Path) -> bool:
    """Return True if the file or any ancestor dir is in the blocked set."""
    # Check file extension
    if path.suffix.lower() in _BLOCKED_EXTENSIONS:
        return True
    # Check exact filename
    if path.name.lower() in _BLOCKED_FILENAMES:
        return True
    # Check if any part of the path goes through a blocked directory name
    for part in path.parts:
        if part.lower() in _BLOCKED_DIRS:
            return True
    return False


def _is_within_root(real_file: Path, real_root: Path) -> bool:
    """Return True if real_file is strictly inside real_root (after resolution)."""
    try:
        real_file.relative_to(real_root)
        return True
    except ValueError:
        return False


def search_files(
    query: str,
    roots: Optional[Sequence[str]] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    """Search for files whose names contain the query string (case-insensitive substring match).

    P0 note: This searches file *names* only — it does NOT read or index file
    contents.  For example, query='budget' will match 'Budget_2026.xlsx' but
    will NOT find the word 'budget' typed inside a .txt file.

    Args:
        query:       Substring to look for in file names (case-insensitive).
        roots:       List of directory paths to search.  If empty or None,
                     returns an error — the user must configure search.roots.
        max_results: Maximum number of results to return (capped at 100).

    Returns:
        Dict with keys:
            ok          – bool
            matches     – list of resolved absolute path strings (ok=True only)
            total_found – count before max_results cap (ok=True only)
            error       – error code string (ok=False only)
            message     – human-readable description (ok=False only)
    """
    if not query or not isinstance(query, str) or not query.strip():
        return {
            "ok": False,
            "error": "empty_query",
            "message": "Query must be a non-empty string.",
        }

    # Validate and resolve roots
    if roots is None:
        effective_roots = load_default_roots()
    else:
        effective_roots = list(roots)

    if not effective_roots:
        return {
            "ok": False,
            "error": "no_roots_configured",
            "message": (
                "No search root directories configured. "
                "Set search.roots in voicecore.toml before using search_files."
            ),
        }

    cap = min(max(1, max_results), 100)
    needle = query.strip().lower()

    # Resolve each root; skip if it doesn't exist as a real directory
    resolved_roots: List[Path] = []
    for r in effective_roots:
        try:
            rp = Path(r).resolve()
            if rp.is_dir():
                resolved_roots.append(rp)
        except (OSError, ValueError):
            continue

    if not resolved_roots:
        return {
            "ok": False,
            "error": "no_valid_roots",
            "message": "None of the configured search roots exist as directories.",
        }

    matches: List[str] = []
    total_found = 0

    for root in resolved_roots:
        for item in root.rglob("*"):
            # Skip directories themselves; skip symlinks without following them
            # (follow_symlinks= param on is_file() is 3.13+; use os.path.islink)
            if os.path.islink(item) or not item.is_file():
                continue

            # Resolve real path (resolves junctions, symlinks, 8.3 names, UNC)
            try:
                real = item.resolve()
            except (OSError, ValueError):
                continue

            # Boundary check on resolved path, not the traversal path
            if not _is_within_root(real, root):
                continue

            # Security: skip blocked files
            if _is_blocked(real):
                continue

            # Filename match (name = stem + suffix, e.g. "budget_q1.xlsx")
            if needle not in real.name.lower():
                continue

            total_found += 1
            if len(matches) < cap:
                # Return the drive-normalized, forward-slash form of the real path
                matches.append(str(real))

    return {
        "ok": True,
        "matches": matches,
        "total_found": total_found,
        "query": query,
        "searched_roots": [str(r) for r in resolved_roots],
    }


def search_files_precheck(args: Dict[str, Any], roots: Optional[Sequence[str]] = None) -> tuple[bool, str]:
    """Pre-check for search_files: roots must be configured and query non-empty."""
    query = args.get("query")
    if not query or not isinstance(query, str) or not query.strip():
        return False, "Query must be a non-empty string."

    effective_roots = list(roots) if roots is not None else load_default_roots()
    if not effective_roots:
        return False, "No search root directories configured in voicecore.toml."

    # Check if at least one root directory actually exists
    valid = False
    for r in effective_roots:
        try:
            rp = Path(r).resolve()
            if rp.is_dir():
                valid = True
                break
        except (OSError, ValueError):
            continue

    if not valid:
        return False, "None of the configured search roots exist as directories on disk."
    return True, ""
