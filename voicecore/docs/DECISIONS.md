# Architecture & Specification Decisions (ADR)

This file records all architectural deviations, decisions, and resolutions against the original specifications in `docs/`.

---

## DECISION-001: Cactus Compute Engine Resolution (`cactus-compute` vs `cactus-needle`)

- **Status:** APPROVED by Vignesh (2026-11-10) with conditions:
  1. Update `docs/03_TECH_STACK.md`, `ANTIGRAVITY_PROMPT.md`, and `setup.ps1` to `cactus-compute`.
  2. No `import cactus as needle` alias; use a single `voicecore.engine` adapter.
  3. Pin `cactus-compute==4.1.0` and record SHA-256 of the wheels and both `.cact` files.
  4. Relabel S4 as “partially verified (parsing only; physical hook test in M2)”.
- **Date:** 2026-11-10
- **Context:**
  - `docs/03_TECH_STACK.md` noted an open discrepancy:
    > "Discrepancy — resolve in spike S1: the Hugging Face `needle3` card shows a different API (`pip install cactus-compute`, `import cactus`, `cactus.Cactus(...)`), while the GitHub README, the Whistle card and the installed package use `cactus-needle` / `import needle`. Use `needle`. Do not mix the two."
  - When executing the contract test `scripts/verify_env.py` using `cactus-needle==3.2.10`:
    - `cactus-needle` hardcoded `ENGINE_REPOS[3] = "Cactus-Compute/needle3"` and `ENGINE_VERSIONS[3] = "3.3.3"`.
    - It attempted to download `https://huggingface.co/Cactus-Compute/needle3/resolve/main/python/cactus_needle-3.3.3-py3-none-win_amd64.whl`.
    - Hugging Face returned **404 Entry Not Found**. Querying the HF API confirmed no `.whl` files exist in `Cactus-Compute/needle3`.
    - Inspection of `needle/agent/fetch.py` revealed a known upstream issue documented by Cactus: `unpublished_engine_wheels(): Pinned engine wheels that are missing from the Hub... leaves every fresh install with nothing to fetch.`
- **Resolution:**
  - Pin dependency: `cactus-compute[mic]==4.1.0`.
  - Upstream maintainers consolidated engine binaries under package `cactus-compute` (4.1.0) and HF repository `Cactus-Compute/cactus` (`releases/4.1.0/python/cactus_runtime-4.1.0-py3-none-win_amd64.whl`).
  - Encapsulate all engine imports through a single module: `voicecore.engine` (`src/voicecore/engine.py`), exposing `tool`, `NeedleAgent` (`cactus.Cactus`), `Whistle`, and `transcribe`. No alias shimming.
  - Telemetry strictly suppressed before engine import via `CACTUS_TELEMETRY=0`, `NEEDLE_TELEMETRY=0`, and `DO_NOT_TRACK=1`.

### Pinned Artifact Hashes (SHA-256)
| Artifact | Source / Location | SHA-256 | Size (Bytes) |
|---|---|---|---|
| `cactus_compute-4.1.0-py3-none-any.whl` | PyPI Release 4.1.0 | `fef19364d14e82fc1fbc850cfd9402fcbbb5a284ab68237b0ea3b9e062d8a9c3` | 132,367 |
| `cactus_runtime-4.1.0-py3-none-win_amd64.whl` | Hugging Face `Cactus-Compute/cactus` | `300f66c30a67e907686edd35f05b45ce82b78ae9449214f6776df983dcb2178f` | 866,115 |
| `needle3.cact` | Hugging Face `Cactus-Compute/needle3` (`d6c7d6a2...`) | `c9d915eca282ed42d1a09b143b592adb4cc6744ffe2d294adf5cfc5548170c38` | 35,335,380 |
| `whistle.cact` | Hugging Face `Cactus-Compute/whistle` (`74111868...`) | `b6e02f048568ac5d01a2042556c658061e699acbc0aa2a1439f52f3d461dffeb` | 16,919,407 |

---

## DECISION-002: CPU Thread Tuning & Runtime Thread Allocation

- **Status:** APPROVED (2026-11-10)
- **Date:** 2026-11-10
- **Context:**
  - On Windows CPUs with asymmetric core architectures (e.g. Intel P/E hybrid cores), the default thread setting (`threads=0`, which spawns threads across all 16 logical cores) causes severe context switching and thread migration across E-cores.
  - This degraded NLU inference p50 from ~300 ms to 1,760 ms, and ASR p50 from 80 ms to 445 ms.
- **Resolution:**
  - Introduce `[runtime] threads = 2` in `config/voicecore.toml` (and `VoiceCoreConfig.runtime.threads`).
  - Add `python -m voicecore --tune-threads` CLI utility to benchmark latency across thread counts (1, 2, 4, 8, auto).
  - Verify `cactus.set_threads(N)` lifecycle: the underlying C runtime supports dynamic thread pool reconfiguration either before or after model load. Configuring it prior to model instantiation ensures optimal memory allocations.

---

## DECISION-003: Host Tool Safety and Always-CONFIRM Default

- **Status:** APPROVED (2026-11-10)
- **Date:** 2026-11-10
- **Context:**
  - Level 1 Plugin API allows external applications to register custom tools.
  - Without guardrails, external tools with high confidence could trigger unauthorized or unvalidated actions without user consent.
- **Resolution:**
  - Host-provided tools default to **always-CONFIRM** (Decision.CONFIRM even at 0.99 confidence) unless the host explicitly supplies both:
    1. An approved risk tier (`T0` read-only or `T1` reversible).
    2. An explicit precheck callable `precheck(args) -> Tuple[bool, str]`.
  - The `@tool` decorator attaches `tier`, `precheck`, and passes `triggers` through to Needle to anchor routing grammar.
  - High-level `VoiceAssistant` facade coordinates `registry`, `policy_gate`, `events`, `ASR`, `Router`, and `push-to-talk`.

---

## DECISION-004: Level-2 (WebSocket Sidecar) Assessment and Architecture Specification

- **Status:** SPECIFIED; IMPLEMENTATION DEFERRED TO P1
- **Date:** 2026-11-10
- **Context:**
  - `docs/07_PLUGIN_CONTRACT.md` proposes two plugin consumption tiers:
    - **Level 1:** In-process Python library (`from voicecore import VoiceAssistant, tool`).
    - **Level 2:** Local WebSocket sidecar (`python -m voicecore --serve --port 8765`) for non-Python frontends (Tauri in Rust, Electron in TypeScript/Node, Flutter in Dart).
  - P0's target application (VYKE) and evaluation harness are 100% Python.
- **Level-2 Technical Specification:**
  1. **Network & Binding:**
     - Must bind exclusively to `127.0.0.1` (loopback). Never `0.0.0.0` or external network adapters.
     - Ephemeral port or configurable `--port` (default `8765`).
  2. **Authentication:**
     - Ephemeral random per-launch Bearer token passed by host via CLI `--token <UUID4>` or environment variable `VOICECORE_AUTH_TOKEN`.
     - Reject WebSocket handshake immediately (HTTP 401) if header `Authorization: Bearer <token>` is missing or invalid.
  3. **Message Protocol:**
     - JSON envelope: `{"v": 1, "type": "<event_or_command>", "payload": { ... }}`
     - **Host -> Core Commands:**
       * `register_tools`: JSON list of tool schemas, risk tiers, and triggers.
       * `start_listening` / `stop_listening`: Trigger push-to-talk capture.
       * `text`: Send raw text query (e.g. for testing / typed UI).
       * `confirm_response`: `{"run_id": "...", "approved": true/false}`.
       * `tool_result`: `{"run_id": "...", "call_id": "...", "result": { ... }}` returning execution output for host-managed tools.
     - **Core -> Host Events:**
       * Dispatches all standard event stream items (`listening_started`, `transcript`, `route`, `gate`, `confirm_request`, `tool_result`, `reminder_due`, `done`).
       * `tool_call_request`: Dispatched when a host-registered tool passes policy gate. Core sends call arguments to host and suspends until host replies with `tool_result` (with 10s timeout).
  4. **Policy Enforcement:**
     - Host-registered tools over WebSocket keep their declared risk tiers, and undergo the exact same `PolicyGate` evaluation (confidence thresholds, precheck validation, negation check) prior to dispatching `tool_call_request`.
- **Resolution for P0:**
  - Level 1 fulfills 100% of P0 requirements with zero serialization overhead, zero IPC socket latency (~0 ms), and complete type safety.
  - Level 2 is fully specified and will be implemented when non-Python frontend integration (Tauri/Electron UI) commences in P1. Thresholds remain frozen at 0.80/0.50 until human audio is evaluated.



