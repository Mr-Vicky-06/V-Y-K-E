# 03 — Tech stack & verification ledger

## Stack
| Layer | Choice | Status |
|-------|--------|--------|
| OS target | Windows 11 | Vignesh's machine; Linux/macOS later |
| Language | Python 3.11+ (tested on Python 3.12) | verified from runtime check |
| ASR | `cactus.Whistle` / `cactus.transcribe` | 16.9 MB, CPU, Apache-2.0 |
| Router | `cactus.Cactus` / `Needle` (Needle 3) | tool calls + confidence, grammar-constrained |
| Mic | `cactus-compute[mic]` → numpy, soxr, sounddevice | verified from package metadata |
| Hotkey | `pynput` | partially verified (parsing only; physical hook test in M2) |
| Tests | pytest | verified |
| Packaging | `pyproject.toml`, src layout, venv + pip (`cactus-compute==4.1.0`) | verified |
| Frameworks | none in P0 | FastAPI/websockets only in M5, only if the spike shows a need |

## Verification ledger
**Verified** (primary sources verified 2026-11-10; package `cactus-compute==4.1.0` installed and live weights loaded):
- Package & Engine Resolution (ADR DECISION-001): `cactus-compute==4.1.0` pinned. Engine binaries loaded from `Cactus-Compute/cactus` runtime container.
- Public API: `cactus.tool`, `cactus.Cactus` (and `Needle = Cactus`), `cactus.Whistle`, `cactus.transcribe`. Encapsulated via a single `voicecore.engine` adapter.
- Telemetry: Disabled before importing via `CACTUS_TELEMETRY=0`, `NEEDLE_TELEMETRY=0`, and `DO_NOT_TRACK=1`.
- S2 Verified: `agent.complete()` returns parsed `function_calls` and `confidence` WITHOUT executing decorated functions. `agent.run()` executes decorated functions.
- S3 Verified: `cactus.transcribe()` accepts `str`, `Path`, and 16 kHz numpy arrays (`float32`, `int16`). Silence returns empty transcript `{"text": "", "language": "", ...}` without errors.

**Partially verified:**
- S4: Hotkey parsing and selective filtering verified with `pynput`; physical global hook test deferred to M2.

**Hypothesis / calibration needed in M4:**
- Latency benchmarks on Vignesh's machine.
- Confidence threshold calibration (start 0.80 ACT, 0.50 CONFIRM).
- Reminder datetime extraction formatting (ISO 8601 vs text parser).
