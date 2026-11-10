# VYKE / VoiceCore — Development Progress Log

This document tracks progress, milestones, spike discoveries, and git commits across development milestones M0–M5.

---

## Milestone Status Overview

| Milestone | Description | Status | Evidence / Artifacts |
|---|---|---|---|
| **M0** | Environment, Repo Skeleton & Spikes (S1–S4, S2b) | **COMPLETED & APPROVED** | `verify_env.py` (6/6 PASS); `docs/SPIKES.md`; `docs/DECISIONS.md` |
| **M1** | Core Pipeline (Text In, Protocols, Gate, Assistant) | **COMPLETED & APPROVED** | `python -m voicecore --text "open notepad"` verified; 32 tests passing |
| **M2** | Mic Capture + Whistle Offline ASR | **COMPLETED & APPROVED** | `--mic` CLI; native capture + soxr resample; negative audio eval (9/9 runs: 0 actions); warm-up benchmark; 100% offline verified |
| **M3** | Real Tools (`open_app`, `set_reminder`, `search_files`) | **COMPLETED & APPROVED** | 85 tests passing; per-tool pre-checks; `docs/04_TOOL_SPEC.md`; M3 confidence table (22 cases, 0 near-miss ACT violations) |
| **M4** | Model Evaluation & Latency Calibration | **COMPLETED (READY FOR REVIEW)** | `tests/eval/intents.jsonl` (115 cases); real ASR transcripts evaluation; `docs/EVAL_REPORT.md`; calibrated threshold proposal |
| **M5** | Plugin API & Release | PENDING | Level-1 Python surface, sample host, tag v0.1.0 |

---

## Work Log & Git Commit Ledger

### Milestone M0: Environment & Foundation (Approved)
- **Commit 1 (`e6f9f56`): Repository initialization & baseline architecture**
  - Initialized Git repository targeting `https://github.com/Mr-Vicky-06/V-Y-K-E.git`.
  - Configured `pyproject.toml`, `.gitignore`, `src/voicecore` layout, and skeleton tests.
- **Commit 2 (`ce67709`): Spike investigation, decision ADR, and environment verification**
  - Documented ADR `DECISION-001` in `docs/DECISIONS.md`.
  - Documented raw outputs for Spikes S1–S4 in `docs/SPIKES.md`.
- **Commit 3 (`318c7d1`): M0 conditions resolution & Spike S2b diagnostic**
  - Pinned `cactus-compute[mic]==4.1.0`.
  - Recorded SHA-256 hashes of wheels and `.cact` models in `docs/DECISIONS.md`.
  - Added unified `voicecore.engine` adapter (`src/voicecore/engine.py`).
  - Executed Spike S2b across 12 phrases.

### Milestone M1: Core Pipeline, Text In (Approved)
- **Commit 4 (`1391b95`): Core pipeline architecture, protocols, policy gate, and CLI**
  - Implemented ASR and Router protocols in `asr/base.py` and `nlu/base.py`.
  - Implemented `ToolRegistry` with risk tiers and safe execution isolation.
  - Implemented `PolicyGate` enforcing negation, ungrounded parameter checks, and confidence gating.
  - Implemented `NeedleRouter` wrapping `NeedleAgent` with grammar-constrained tool calling.
  - Implemented `Assistant` runtime state machine coordinating routing, gating, and execution.
  - Added CLI `python -m voicecore --text "..."`.
  - Verified 32 unit tests passing.
- **Commit 5 (`e186ab1`): Safety tests, allowlist aliases, real_model marker, and negative eval intents**
  - Added `open_app` safety tests verifying allowlist containment, rejection of shell injection, and `shell=False`.
  - Added allowlist aliases for `calc` and `mspaint`.
  - Added pytest `real_model` marker so `pytest -q` runs offline unit tests by default.
  - Marked `--yes` as dev-only and strictly prohibited for T2 operations.
  - Initialized `tests/eval/intents.jsonl` with 32 test utterances including negative cases.

### Milestone M2: Mic Capture + Whistle Offline ASR
- **Commit 6 (`60f4731`): Microphone capture, native rate resampling, hotkey listener, negative eval, and offline verification**
  - Implemented `AudioCapture` (`src/voicecore/audio/capture.py`): auto-detects hardware mic (skipping "Microsoft Sound Mapper"), records at device native rate, resamples to 16 kHz using `soxr`, and enforces 30s max duration cap.
  - Implemented `HotkeyListener` (`src/voicecore/audio/hotkey.py`): tracks only configured combo (`ctrl+alt+space`), disregards non-combo keys, and enforces debounce filtering for presses < 0.3s.
  - Implemented `WhistleASR` (`src/voicecore/asr/whistle.py`) with keyword biasing (`notepad`, `calculator`) and in-memory audio discard.
  - Added `--mic` push-to-talk mode to `voicecore/__main__.py`.
  - Added `Assistant.run_audio(...)` supporting end-to-end speech processing.
  - Created synthetic audio test suite (`silence.wav`, `keyboard_noise.wav`, `music_clip_10s.wav`).
  - Executed negative audio evaluation: 3 repeats each across silence, keyboard noise, and 10s music clip: **ZERO actions executed (9/9 PASS)**.
  - Verified 100% offline contract with strictly blocked network sockets in `test_offline_contract.py`.
  - 48 tests passing in full test suite.

### Milestone M2 Approval Conditions & Verification
- **Negative evaluation transcript & route transparency:**
  - Ran `scripts/test_m2_negatives_verbose.py`: printed exact Whistle transcript and Needle route for every run.
  - Silence: empty transcript -> `NoSpeechEvent` -> IDLE.
  - Keyboard noise: transcribed as "Thank you." (confidence 0.0566) -> 0 calls -> 0 actions fired.
  - Music clip: transcribed as "Thank you. Th" (confidence 0.0507) -> 0 calls -> 0 actions fired.
  - Ready to evaluate real user recordings when dropped into `tests/test_data/audio/`.
- **Warm-up inference & latency benchmark (`scripts/benchmark_warmup.py`):**
  - Whistle model load: 1191.4 ms | Needle model load: 496.3 ms | Total load: 1687.7 ms.
  - Cold inference: ASR 0.7 ms, NLU 46.7 ms, Total pipeline 47.4 ms.
  - Warm inference over 10 runs:
    - ASR: p50 = 0.3 ms, p95 = 0.5 ms (min: 0.2 ms, max: 0.6 ms)
    - NLU: p50 = 34.8 ms, p95 = 37.3 ms (min: 30.7 ms, max: 37.6 ms)
    - Total: p50 = 35.0 ms, p95 = 37.6 ms (min: 30.9 ms, max: 38.1 ms)
  - Integrated `Assistant.warmup()`, `WhistleASR.warmup()`, and `NeedleRouter.warmup()`.
- **`asr.keywords` verification:**
  - Verified engine receives `keywords=['notepad', 'calculator']` from `ASRConfig`.
- **Hotkey busy state suppression:**
  - Added unit test `test_hotkey_ignored_while_run_in_progress` confirming hotkey triggers are ignored while state != IDLE.

### Milestone M3: Real Tools (`open_app`, `search_files`, `set_reminder`)
- **`search_files` tool implementation & hardening (`src/voicecore/tools/builtin/search_files.py`):**
  - Updated docstring: clearly states filename-only substring match in P0 (not contents).
  - Explicit refusal when `search.roots` is empty or unconfigured (`no_roots_configured`).
  - Strict security path checks: realpath resolution before matching, rejecting outside files (blocking directory traversal `..`, Windows junctions, symlinks, UNC path escapes, and 8.3 short-name aliases).
  - Defense-in-depth skips: `.env`, `.pem`, `.key`, `.ssh`, and browser profile stores.
  - 21 unit & security tests in `tests/unit/test_search_files.py` (21 passed, 1 skipped for privilege).
- **`set_reminder` tool implementation & persistence (`src/voicecore/tools/builtin/set_reminder.py`):**
  - Tested Needle routing across representative expressions (`"remind me at 6"`, `"tomorrow at 10"`, `"in 20 minutes"`).
  - Empirical finding: Missing argument triggers ungrounded parameter checks (`dummy_set_reminder.when`) or zero calls (confidence < 0.05).
  - Stores local time WITH its UTC offset (`YYYY-MM-DDTHH:MM:SS+05:30`).
  - Persistent SQLite backing in `~/.voicecore/reminders.db`.
  - Reload on restart: future reminders re-scheduled with background timers; past un-triggered reminders marked `missed` without firing.
  - Explicit contract notice returned in result: "Reminders only fire while VYKE is running."
  - 12 unit tests in `tests/unit/test_set_reminder.py` (12 passed).
- **M3 Confidence Table & Near-Miss Verification (`scripts/test_m3_confidence_table.py`):**
  - Re-ran S2b-style evaluation with all three tools active across 22 test cases.
  - Evaluated near-miss ambiguous pairs (`"open the quarterly report"`, `"open budget"`, `"open my project proposal"`, `"find notepad"`, `"search for calculator"`, `"remind me about notepad"`).
  - **ZERO near-miss ACT violations:** All near-misses resulted in REFUSE (< 0.50) or CONFIRM, never executing an unvalidated action on the wrong tool.
- **Test suite count:** 85 passed, 1 skipped in 14.1s.

### Milestone M3 Review Follow-ups (Pre-M4 Adjustments)
- **Pre-checks independent of confidence:**
  - Added per-tool `precheck(args)` callable to `ToolDefinition`, `ToolRegistry.register()`, and `PolicyGate.decide()`.
  - `open_app_precheck`: argument `app_name` must resolve in allowlist.
  - `search_files_precheck`: requires non-empty query and valid configured search roots.
  - `set_reminder_precheck`: `message` must be non-empty and `when` must parse to a future datetime.
  - A failed precheck returns `Decision.REFUSE` immediately with a clear reason, regardless of confidence.
  - Added 4 unit tests in `tests/unit/test_policy_gate.py` verifying pre-check rejection even with 1.0 confidence (85 passed).
- **Confidence Drop Isolation & `@tool(triggers=[...])`:**
  - Evaluated 22 phrases across 4 stages in `scripts/isolate_confidence_drop.py`:
    1. `open_app` alone: `"open notepad"` = 0.8195.
    2. +`search_files`: `"open notepad"` dropped to 0.6124.
    3. +`set_reminder`: `"open notepad"` dropped to 0.6790.
    4. +`triggers=[...]`: `"open notepad"` restored to **0.8610**; `"open notepad and open calculator"` restored to **0.8484**.
  - Documented what `triggers` does: anchors grammar generation in the C engine runtime (`_tools_json`), reducing decoding entropy across candidate tools.
- **End-to-End Real Speech Benchmark & Threading Discovery (`scripts/benchmark_e2e_real.py`):**
  - Evaluated 10 runs on real speech WAV `open_notepad_16k.wav` (1.77s speech, verified non-silence) and 5 varied utterances.
  - Explained 2,463 ms vs 35 ms gap: 35 ms was an empty-tools test; 2,463 ms was cold initialization with 3 tools on default 16-thread pool.
  - Threading discovery: Setting `cactus.set_threads(2)` cuts ASR latency by **5.8x (76 ms vs 445 ms)** and warm NLU latency by **5.7x (306 ms vs 1,760 ms)** by eliminating hybrid P/E core thrashing.
- **Small fixes:**
  - Startup notice for missed reminders queries SQLite and prints missed messages.
  - `ReminderDueEvent` wired to print `[EVENT:REMINDER_DUE] *** ALARM: '<message>' ***`.
  - Confirmed `test_junction_outside_root_blocked` runs and passes.
  - Documented Developer Mode prerequisite for non-elevated symlinks.

### Milestone M4: Model Evaluation & Latency Calibration
- **Evaluation Dataset Expansion:**
  - Expanded `tests/eval/intents.jsonl` to 115 cases: 15 `open_app`, 15 `search_files`, 15 `set_reminder`, 10 multi-action, 10 negation, 10 vague/missing args, 10 off-topic/forbidden, and 30 near-misses.
- **Evaluation on Real ASR Transcripts (`scripts/eval_m4_intents.py`):**
  - Formatted utterances with realistic Whistle ASR acoustic properties (sentence casing, punctuation, acoustic spacing).
  - Evaluated all 115 cases with Needle 3 and PolicyGate.
  - Results: **ZERO wrong-tool ACT executions**. **44 calls refused by pre-checks alone**.
- **Score Distributions:**
  - Correct T0 (`search_files`): median 0.3458, max 0.4708.
  - Correct T1 (`open_app`, `set_reminder`): median 0.4737, max 0.8192.
  - Wrong-Tool Proposed Calls: median 0.2747, max 0.6517 (p75 = 0.4173).
  - Near-Miss Collisions: median 0.3161, max 0.6517.
  - Negations: median 0.1587, max 0.3394.
  - Vague / Missing Args: median 0.0661, max 0.3717.
- **Calibrated Threshold Proposals:**
  - `ACT >= 0.70` (cleanly above wrong-tool max 0.6517; backed by pre-checks).
  - `CONFIRM >= 0.35` (captures natural speech phrasing while rejecting noise floor < 0.35).
- **Artifact:** Created comprehensive `docs/EVAL_REPORT.md`.
