# VYKE / VoiceCore — Development Progress Log

This document tracks progress, milestones, spike discoveries, and git commits across development milestones M0–M5.

---

## Milestone Status Overview

| Milestone | Description | Status | Evidence / Artifacts |
|---|---|---|---|
| **M0** | Environment, Repo Skeleton & Spikes (S1–S4) | **IN PROGRESS** | Skeleton created; venv setup; S1–S4 spikes underway |
| **M1** | Core Pipeline (Text In, Protocols, Gate, Assistant) | PENDING | Acceptance per `docs/08_TESTING_VERIFICATION.md` |
| **M2** | Mic Capture + Whistle Offline ASR | PENDING | Push-to-talk capture + offline speech-to-text proof |
| **M3** | Real Tools (`open_app`, `set_reminder`, `search_files`) | PENDING | Security unit tests + allowlists |
| **M4** | Model Evaluation & Latency Calibration | PENDING | `tests/eval/intents.jsonl`, latency metrics, `docs/EVAL_REPORT.md` |
| **M5** | Plugin API & Release | PENDING | Level-1 Python surface, sample host, tag v0.1.0 |

---

## Work Log & Git Commit Ledger

### Milestone M0: Environment & Foundation
- **Commit 1: Repository initialization & baseline architecture**
  - Initialized Git repository targeting `https://github.com/Mr-Vicky-06/V-Y-K-E.git`.
  - Added root and package `.gitignore` files to safeguard against committing virtualenvs, model weights (`.cact`, `.safetensors`), and bytecode.
  - Established `src/voicecore` layout: `audio/`, `asr/`, `nlu/`, `policy/`, `tools/`, `runtime/`, `plugin/`.
  - Configured `pyproject.toml` with project metadata, dependencies (`cactus-needle[mic]`, `pynput`, `pytest`), and pytest discovery.
  - Added smoke unit test in `tests/unit/test_skeleton.py`.
  - Created top-level `README.md` and initial `docs/PROGRESS.md`.

---

## Technical Spike Findings (M0)

### S1: Package & Engine Verification (`needle` vs `cactus`)
- **Status:** Investigating engine distribution & wheel resolution.
- **Installed Package:** `cactus-needle` 3.2.10 (PyPI latest) with `import needle`.
- **Finding:** Hugging Face model repository `Cactus-Compute/needle3` hosts `.cact` weights and safetensors, while compiled engine wheels (`libneedle.dll`) and binary distributions are tracked across `Cactus-Compute/needle2` and `Cactus-Compute/cactus`. Detailed in `docs/SPIKES.md`.

---

## Next Steps
1. Complete S1–S4 spikes and document findings in `docs/SPIKES.md`.
2. Run `scripts/verify_env.py` and document exact outputs.
3. Submit M0 milestone report for review before proceeding to M1.
