# 03 — Tech stack & verification ledger

## Stack
| Layer | Choice | Status |
|-------|--------|--------|
| OS target | Windows 11 | Vignesh's machine; Linux/macOS later |
| Language | Python 3.11+ (cactus-needle declares `>=3.9`) | verified from package metadata |
| ASR | `needle.Whistle` / `needle.transcribe` | 16.9 MB, CPU, Apache-2.0 |
| Router | `needle.Needle` (Needle 3) | tool calls + confidence, grammar-constrained |
| Mic | `cactus-needle[mic]` → numpy, soxr, sounddevice | verified from package metadata |
| Hotkey | `pynput` (candidate) | hypothesis; validate in spike S4 |
| Tests | pytest | |
| Packaging | `pyproject.toml`, src layout, venv + pip | no extra tooling |
| Frameworks | none in P0 | FastAPI/websockets only in M5, only if the spike shows a need |

## Verification ledger
**Verified** (primary sources read 2026-11-10; package `cactus-needle` 3.2.10 installed and introspected):
- Core dependency is only `huggingface_hub`; extras: `mic`, `train`, `gpu`, `metal`, `compare`, `test`, `mlx`.
- Public API: `needle.tool` (decorator, optional `triggers=`); `needle.Needle(tools, system, weights, tool_index_path, buffer_size, auto_date, generation, stateless)` with `run`, `complete`, `embed`, `extract`, `reset`, `close`, context manager; `needle.Whistle(weights, buffer_size)` with `transcribe`, `stream`, `embed`; `needle.transcribe(audio, language, keywords, word_timestamps, weights)`; `needle.stream(chunks, language, keywords, weights)`.
- README: each turn returns JSON with `function_calls`, `reasoning`, `confidence`; an off-topic request returns an empty list; telemetry on by default, disabled by the env vars in 02.
- Whistle card: 16 kHz mono; single pass ≤30 s, windowed beyond; silence/steady noise → empty transcript; music can still yield text; keyword biasing via `keywords=[...]`; mic capture needs `[mic]`.

**Discrepancy — resolve in spike S1:** the Hugging Face `needle3` card shows a different API (`pip install cactus-compute`, `import cactus`, `cactus.Cactus(...)`), while the GitHub README, the Whistle card and the installed package use `cactus-needle` / `import needle`. Use `needle`. Do not mix the two.

**Not verified (hypothesis / unknown):**
- Runtime shape of `run()` / `complete()` return values (weights could not be downloaded in the research sandbox) → S2.
- Whether `complete()` returns calls **without executing** decorated functions (the policy gate needs this) → S2.
- Where `confidence` sits in the result and what thresholds make sense → S2, calibrate in M4.
- Latency on Vignesh's CPU → M4.
- Whether "remind me at 6" becomes a usable datetime argument → M4 eval.
- Hotkey behaviour on his Windows setup → S4.
