# VYKE / VoiceCore — Development Progress Log

This document tracks progress, milestones, spike discoveries, and git commits across development milestones M0–M5.

---

## Milestone Status Overview

| Milestone | Description | Status | Evidence / Artifacts |
|---|---|---|---|
| **M0** | Environment, Repo Skeleton & Spikes (S1–S4) | **READY FOR REVIEW** | `verify_env.py` (6/6 PASS); `docs/SPIKES.md`; `docs/DECISIONS.md` |
| **M1** | Core Pipeline (Text In, Protocols, Gate, Assistant) | PENDING | Acceptance per `docs/08_TESTING_VERIFICATION.md` |
| **M2** | Mic Capture + Whistle Offline ASR | PENDING | Push-to-talk capture + offline speech-to-text proof |
| **M3** | Real Tools (`open_app`, `set_reminder`, `search_files`) | PENDING | Security unit tests + allowlists |
| **M4** | Model Evaluation & Latency Calibration | PENDING | `tests/eval/intents.jsonl`, latency metrics, `docs/EVAL_REPORT.md` |
| **M5** | Plugin API & Release | PENDING | Level-1 Python surface, sample host, tag v0.1.0 |

---

## Work Log & Git Commit Ledger

### Milestone M0: Environment & Foundation
- **Commit 1 (`e6f9f56`): Repository initialization & baseline architecture**
  - Initialized Git repository targeting `https://github.com/Mr-Vicky-06/V-Y-K-E.git`.
  - Added root and package `.gitignore` files to safeguard against committing virtualenvs, model weights (`.cact`, `.safetensors`), and bytecode.
  - Established `src/voicecore` layout: `audio/`, `asr/`, `nlu/`, `policy/`, `tools/`, `runtime/`, `plugin/`.
  - Configured `pyproject.toml` with project metadata and dependencies.
  - Added skeleton unit test in `tests/unit/test_skeleton.py`.
  - Created top-level `README.md` and initial `docs/PROGRESS.md`.
- **Commit 2: Spike investigation, decision ADR, and environment verification**
  - Documented ADR `DECISION-001` in `docs/DECISIONS.md` resolving engine migration from `cactus-needle` to `cactus-compute`.
  - Documented complete raw outputs for Spikes S1, S2, S3, and S4 in `docs/SPIKES.md`.
  - Updated `scripts/verify_env.py` and `scripts/setup.ps1` to test the live runtime and privacy guardrails.
  - Verified 6/6 tests passing in `scripts/verify_env.py` and green `pytest`.

---

## Technical Spike Findings (M0)

### S1: Package & Engine Verification (`needle` vs `cactus`)
- **Status:** **VERIFIED**
- **Finding:** Upstream maintainers consolidated engine binaries under `cactus-compute` v4.1.0 (with wheels in `Cactus-Compute/cactus`). `cactus-compute` provides an exact alias `Needle = Cactus`, while downloading `needle3.cact` and `whistle.cact`. All telemetry suppressed via `CACTUS_TELEMETRY=0`, `NEEDLE_TELEMETRY=0`, and `DO_NOT_TRACK=1`.

### S2: Return Shapes of `run()` and `complete()`
- **Status:** **VERIFIED**
- **Finding:** `run()` executes functions directly (returns `results`). `complete()` returns proposed `function_calls` without executing the underlying Python function, allowing `PolicyGate` to intervene. `confidence` is a top-level float (e.g. 0.957). `stateless=True` disables conversation context carry-over.

### S3: `transcribe` Input Formats & Silence Behavior
- **Status:** **VERIFIED**
- **Finding:** Supports file paths (`str`, `pathlib.Path`) and 16 kHz numpy arrays (`float32` in `[-1.0, 1.0]`, `int16`). On silence, returns `{'text': '', 'language': '', 'ttft_ms': 0.0, 'decode_tps': 0.0}` with zero errors.

### S4: Hotkey Listener Security (`pynput`)
- **Status:** **VERIFIED**
- **Finding:** `pynput.keyboard.HotKey` listening to `<ctrl>+<alt>+<space>` filters all non-configured keys, preventing keystroke logging.
