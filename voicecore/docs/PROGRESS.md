# VYKE / VoiceCore — Development Progress Log

This document tracks progress, milestones, spike discoveries, and git commits across development milestones M0–M5.

---

## Milestone Status Overview

| Milestone | Description | Status | Evidence / Artifacts |
|---|---|---|---|
| **M0** | Environment, Repo Skeleton & Spikes (S1–S4, S2b) | **COMPLETED & APPROVED** | `verify_env.py` (6/6 PASS); `docs/SPIKES.md` (S1–S4, S2b); `docs/DECISIONS.md` (DECISION-001) |
| **M1** | Core Pipeline (Text In, Protocols, Gate, Assistant) | **READY FOR REVIEW** | `python -m voicecore --text "open notepad"` verified; 32 tests passing; acceptance proof documented |
| **M2** | Mic Capture + Whistle Offline ASR | PENDING | Push-to-talk capture + offline speech-to-text proof |
| **M3** | Real Tools (`open_app`, `set_reminder`, `search_files`) | PENDING | Security unit tests + allowlists |
| **M4** | Model Evaluation & Latency Calibration | PENDING | `tests/eval/intents.jsonl`, latency metrics, `docs/EVAL_REPORT.md` |
| **M5** | Plugin API & Release | PENDING | Level-1 Python surface, sample host, tag v0.1.0 |

---

## Work Log & Git Commit Ledger

### Milestone M0: Environment & Foundation (Approved)
- **Commit 1 (`e6f9f56`): Repository initialization & baseline architecture**
  - Initialized Git repository targeting `https://github.com/Mr-Vicky-06/V-Y-K-E.git`.
  - Added root and package `.gitignore` files to safeguard against committing virtualenvs, model weights (`.cact`, `.safetensors`), and bytecode.
  - Established `src/voicecore` layout: `audio/`, `asr/`, `nlu/`, `policy/`, `tools/`, `runtime/`, `plugin/`.
  - Configured `pyproject.toml` with project metadata and dependencies.
  - Added skeleton unit test in `tests/unit/test_skeleton.py`.
  - Created top-level `README.md` and initial `docs/PROGRESS.md`.
- **Commit 2 (`ce67709`): Spike investigation, decision ADR, and environment verification**
  - Documented ADR `DECISION-001` in `docs/DECISIONS.md` resolving engine migration from `cactus-needle` to `cactus-compute`.
  - Documented complete raw outputs for Spikes S1, S2, S3, and S4 in `docs/SPIKES.md`.
  - Updated `scripts/verify_env.py` and `scripts/setup.ps1` to test the live runtime and privacy guardrails.
  - Verified 6/6 tests passing in `scripts/verify_env.py` and green `pytest`.
- **Commit 3 (`318c7d1`): M0 conditions resolution & Spike S2b diagnostic**
  - Pinned `cactus-compute[mic]==4.1.0` in `pyproject.toml` and `setup.ps1`.
  - Recorded exact SHA-256 checksums of wheels and `.cact` models in `docs/DECISIONS.md`.
  - Added unified `voicecore.engine` adapter (`src/voicecore/engine.py`).
  - Relabeled S4 as partially verified (parsing only; physical hook test in M2).
  - Executed Spike S2b across 12 phrases; validated `negation`, `ungrounded`, and `confidence` thresholds.

### Milestone M1: Core Pipeline, Text In
- **Commit 4: Core pipeline architecture, protocols, policy gate, and CLI**
  - Implemented `asr/base.py` (`Transcript`, `ASR` Protocol) and `nlu/base.py` (`ToolCall`, `RouteResult`, `Router` Protocol).
  - Implemented `voicecore.config` loading `config/voicecore.toml` with threshold validation.
  - Implemented thread-safe synchronous `EventBus` and dataclass events in `events.py`.
  - Implemented `ToolRegistry` with risk tiers (T0/T1/T2), schema export, and safe execution isolation.
  - Implemented `PolicyGate` enforcing negation refusal, ungrounded parameter checks, T2 restriction, and confidence thresholds.
  - Implemented `NeedleRouter` wrapping `NeedleAgent` with grammar-constrained tool calling.
  - Implemented `Assistant` runtime state machine adhering to the workflow states in `docs/05`.
  - Built CLI entrypoint `voicecore/__main__.py` supporting `--text "..."` and `--dry-run`.
  - Implemented 32 unit and integration tests across all modules (100% passing in 1.70s).
  - Successfully verified M1 acceptance proof: `python -m voicecore --text "open notepad"`.

---

## Technical Spike Findings (M0 & M1)

### S1: Package & Engine Verification
- **Status:** **VERIFIED**
- **Finding:** Engine binaries consolidated under `cactus-compute==4.1.0`. All imports routed via `voicecore.engine`.

### S2: Return Shapes of `run()` and `complete()`
- **Status:** **VERIFIED**
- **Finding:** `complete()` parses arguments into `function_calls` and extracts `confidence` without running decorated tools, allowing `PolicyGate` evaluation.

### S2b: Edge-Case Evaluation of `complete()`
- **Status:** **VERIFIED**
- **Finding:** Validated 12 edge cases. Explicit negations trigger `validation.negation=True` and call suppression; ungrounded parameters populate `validation.ungrounded`; off-topic queries yield low confidence (< 0.22) or zero calls.

### S3: `transcribe` Input Formats & Silence Behavior
- **Status:** **VERIFIED**
- **Finding:** Supports file paths (`str`, `Path`) and 16 kHz numpy arrays. Silence returns empty transcript without errors.

### S4: Hotkey Listener Security (`pynput`)
- **Status:** **Partially verified (parsing only; physical hook test in M2)**
- **Finding:** `pynput.keyboard.HotKey` listening to `<ctrl>+<alt>+<space>` filters all non-configured keys.
