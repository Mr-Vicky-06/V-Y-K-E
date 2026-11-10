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
