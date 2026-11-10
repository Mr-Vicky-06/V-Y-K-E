# VYKE / VoiceCore — Development Progress Log

This document tracks progress, milestones, spike discoveries, and git commits across development milestones M0–M5.

---

## Milestone Status Overview

| Milestone | Description | Status | Evidence / Artifacts |
|---|---|---|---|
| **M0** | Environment, Repo Skeleton & Spikes (S1–S4, S2b) | **COMPLETED & APPROVED** | `verify_env.py` (6/6 PASS); `docs/SPIKES.md`; `docs/DECISIONS.md` |
| **M1** | Core Pipeline (Text In, Protocols, Gate, Assistant) | **COMPLETED & APPROVED** | `python -m voicecore --text "open notepad"` verified; 32 tests passing |
| **M2** | Mic Capture + Whistle Offline ASR | **READY FOR REVIEW** | `--mic` CLI; native audio capture + soxr resample; negative audio eval (9/9 runs: 0 actions); 100% offline verified |
| **M3** | Real Tools (`open_app`, `set_reminder`, `search_files`) | PENDING | Security unit tests + allowlists |
| **M4** | Model Evaluation & Latency Calibration | PENDING | `tests/eval/intents.jsonl`, latency metrics, `docs/EVAL_REPORT.md` |
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
- **Commit 6: Microphone capture, native rate resampling, hotkey listener, negative eval, and offline verification**
  - Implemented `AudioCapture` (`src/voicecore/audio/capture.py`): auto-detects hardware mic (skipping "Microsoft Sound Mapper"), records at device native rate, resamples to 16 kHz using `soxr`, and enforces 30s max duration cap.
  - Implemented `HotkeyListener` (`src/voicecore/audio/hotkey.py`): tracks only configured combo (`ctrl+alt+space`), disregards non-combo keys, and enforces debounce filtering for presses < 0.3s.
  - Implemented `WhistleASR` (`src/voicecore/asr/whistle.py`) with keyword biasing (`notepad`, `calculator`) and in-memory audio discard.
  - Added `--mic` push-to-talk mode to `voicecore/__main__.py`.
  - Added `Assistant.run_audio(...)` supporting end-to-end speech processing.
  - Created synthetic audio test suite (`silence.wav`, `keyboard_noise.wav`, `music_clip_10s.wav`).
  - Executed negative audio evaluation: 3 repeats each across silence, keyboard noise, and 10s music clip: **ZERO actions executed (9/9 PASS)**.
  - Verified 100% offline contract with strictly blocked network sockets in `test_offline_contract.py`.
  - 48 tests passing in full test suite.
