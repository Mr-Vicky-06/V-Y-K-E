# 06 — Security & permissions

## Threat model (what can go wrong with a voice → action system)
1. **Mis-hearing / mis-routing** (ASR or model error) triggers a wrong action.
2. **Ambient audio** (TV, music, other people) triggers actions. Whistle can emit text for music.
3. **Model output treated as trusted** (path, command, URL) → injection into the OS.
4. **Data leaving the machine** (telemetry, logs with audio, cloud calls).
5. **Privilege creep** as tools are added.

## Controls
| Threat | Control |
|--------|---------|
| 1 | Tier + confidence gate; allowlists; strict argument validation; T2 disabled in P0 |
| 2 | Push-to-talk only in P0. Always-on mic requires VAD **and** wake word (separate milestone, with its own negative-audio tests) |
| 3 | No `shell=True`; no string-built commands; `open_app` via allowlist; `search_files` confined to configured roots with real-path checks; reject unknown tool names |
| 4 | `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1` set before importing `needle`; no network calls in runtime code (a test asserts this); audio kept in memory only and discarded after transcription unless `debug.save_audio=true` |
| 5 | Every new tool needs a tier, a test, an eval case, and an entry in 04 before merge |

## Confidence gate (initial values are **hypotheses**, to be calibrated in M4)
- `confidence ≥ act_threshold` (start 0.80) → ACT for T0/T1.
- `confirm_threshold ≤ confidence < act_threshold` (start 0.50) → CONFIRM.
- below `confirm_threshold` or empty call list → REFUSE / "nothing to do".
- T2 → always CONFIRM regardless of confidence.
Thresholds live in `voicecore.toml`. The agent must not tune them to make tests pass without recording the eval evidence.

## Logging
Structured local log (JSONL) with transcript text, calls, decisions, results. No audio. Rotate/size-cap. A `--no-log` flag disables it.

## Windows specifics
Run as a normal user, never elevated. A global keyboard hook is a keylogger-shaped capability: the hotkey listener must register **only** the configured combo and must not record or log other keystrokes (test for it).
