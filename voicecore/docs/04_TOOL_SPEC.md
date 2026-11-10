# 04 — Tool specification

Design rules (from Needle's tool-design guidance): **one tool per action**, names a user would actually say, formats stated in the description, constraints in the schema, no overlapping tools. Needle takes the signature as argument types and the docstring as the description (`@needle.tool`), so docstrings are part of the interface — treat changes to them as behaviour changes and re-run the eval.

## Risk tiers
| Tier | Meaning | P0 tools | Default gate |
|------|---------|----------|--------------|
| T0 | read-only, local | `search_files` | ACT if confidence ≥ act_threshold |
| T1 | reversible, local, bounded | `open_app`, `set_reminder` | ACT if confidence ≥ act_threshold, else CONFIRM |
| T2 | destructive / external / privileged | none in P0 | always CONFIRM; **not implemented in P0** |

## P0 tools
### `open_app(app_name: str)` — T1
"Open an application by name, for example notepad, calculator, chrome."
- Resolve `app_name` (lower-cased, trimmed) through `config/apps.allowlist.json` (name → executable path or URI). Not in allowlist → return `{"ok": false, "error": "not_allowed"}`; never guess.
- Launch with `subprocess.Popen([...])` or `os.startfile`; **never `shell=True`**, never pass model text into a command line.

### `set_reminder(message: str, when: str)` — T1
"Set a reminder with a message at a future date or time, for example 'tomorrow at 10', 'in 20 minutes', or ISO format."
- Accepts `message: str` and `when: str`.
- Parses relative offsets ("in 20 minutes"), natural phrases ("tomorrow at 10", "at 6pm"), partial Needle strings ("2026-11-11 10"), and ISO 8601 strings.
- Stores local time WITH its UTC offset (e.g. `2026-11-11T10:00:00+05:30`) in SQLite (`~/.voicecore/reminders.db`).
- Reload on restart: future reminders re-arm timers; past-due un-triggered reminders are marked `missed` and do NOT fire.
- Operational constraint: **Reminders only fire while VYKE is running.**

### `search_files(query: str)` — T0
"Search for files whose names contain the query string (case-insensitive substring match). P0 searches file names only (not file contents)."
- Query is treated strictly as a case-insensitive filename substring (stem + extension).
- Searches only folders configured in `voicecore.toml → [search].roots`.
- Refuses clearly with `no_roots_configured` when no roots are set or when roots do not exist.
- Resolves real paths and rejects results outside roots (preventing traversal, symlink escapes, junction escapes, UNC escapes, and 8.3 short-name aliases).
- Always skips `.env`, `.pem`, `.key`, `.ssh`, and browser profile stores.
- Capped by `max_results` (clamped to 100 max). Content search is deferred to later milestones.

## Registry rules
- Tools are registered explicitly (`registry.register(fn, tier=...)`); no auto-discovery, no dynamic import from model output.
- Each tool returns a JSON-serialisable dict with `ok: bool`; errors never raise to the runtime loop.
- `registry.export_schema()` emits JSON (name, description, parameters, tier) — the same file feeds docs, tests and the future phone port.

## Extension order (one at a time, evaluate between each)
1. `list_reminders` / `cancel_reminder` 2. volume/brightness (T1) 3. `search_files` content search 4. window management 5. anything T2.
