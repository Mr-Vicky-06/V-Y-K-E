# Architecture & Specification Decisions (ADR)

This file records all architectural deviations, decisions, and resolutions against the original specifications in `docs/`.

---

## DECISION-001: Cactus Compute Engine Resolution (`cactus-compute` vs `cactus-needle`)

- **Status:** Proposed & Verified via Spikes S1 & S2 (Pending Vignesh's approval at M0)
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
  - The upstream maintainers consolidated the engine releases under the package `cactus-compute` (current version: `4.1.0`) and HF repository `Cactus-Compute/cactus` (`releases/4.1.0/python/cactus_runtime-4.1.0-py3-none-win_amd64.whl`).
  - `cactus-compute` uses the exact same model weights (`needle3.cact` from `Cactus-Compute/needle3` and `whistle.cact` from `Cactus-Compute/whistle`).
  - `cactus-compute` natively exports `Needle = Cactus`, `Whistle = Whistle`, `tool = tool`, and `transcribe = transcribe`.
  - Both `CACTUS_TELEMETRY=0` and `NEEDLE_TELEMETRY=0` with `DO_NOT_TRACK=1` are supported and enforced.
  - To preserve complete compatibility with the codebase and protocols, we provide a transparent bridge/alias (`import cactus as needle` or shim) so that all internal modules can reference either or both.
- **Evidence:**
  - Whistle transcription on 1s silence: returned `{'text': '', 'language': '', 'ttft_ms': 0.0, 'decode_tps': 0.0}` with zero errors.
  - Needle 3 tool call (`get_weather`): `complete()` returned `function_calls` without executing the tool in 0.70s with confidence `0.957` and peak RAM 131 MB.
  - All 6 verification checks passed.
