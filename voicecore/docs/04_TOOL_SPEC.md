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
"Set a reminder. `when` is a local date-time in ISO 8601, for example 2026-11-10T18:00."
- Validate `when` parses and is in the future; ambiguous/missing → `{"ok": false, "error": "bad_time"}` and ask the user (CONFIRM-style prompt), do not invent a time.
- Persist to a local JSON/SQLite file; a scheduler thread fires them and emits a `reminder_due` event.
- Open decision (PRD #2): if the eval shows Needle cannot produce ISO strings reliably, switch the argument to `when_text: str` and parse deterministically (e.g., a small parser), keeping the same tool name.

### `search_files(query: str)` — T0
"Search the user's files by file name or keyword."
- Searches only folders listed in `voicecore.toml → [search].roots`. Resolve real paths and reject anything outside the roots (path-traversal and symlink escape).
- P0: filename match only. Cap results (e.g., 10). Return paths + modified time. Content search/embeddings (`Needle.embed`) are a later extension.

## Registry rules
- Tools are registered explicitly (`registry.register(fn, tier=...)`); no auto-discovery, no dynamic import from model output.
- Each tool returns a JSON-serialisable dict with `ok: bool`; errors never raise to the runtime loop.
- `registry.export_schema()` emits JSON (name, description, parameters, tier) — the same file feeds docs, tests and the future phone port.

## Extension order (one at a time, evaluate between each)
1. `list_reminders` / `cancel_reminder` 2. volume/brightness (T1) 3. `search_files` content search 4. window management 5. anything T2.
