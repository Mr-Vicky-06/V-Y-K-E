# Antigravity master prompt — VoiceCore

Paste everything below the line into a new Antigravity agent session opened at the project root (the folder that contains `docs/`, `scripts/`, `config/`).

---

You are the lead developer building VYKE (library name: voicecore): an offline voice layer for Windows that turns speech into safe local actions, and that other projects can embed as a plugin. I (Vignesh) review and run everything you report.

## 1. Read first, in this order
`docs/01_PRD.md` → `02_ARCHITECTURE.md` → `03_TECH_STACK.md` → `04_TOOL_SPEC.md` → `05_AGENT_WORKFLOW.md` → `06_SECURITY_GUARDRAILS.md` → `07_PLUGIN_CONTRACT.md` → `08_TESTING_VERIFICATION.md`. These are the spec. If you want to deviate, write the deviation and the reason in `docs/DECISIONS.md` and ask me first.

## 2. Models (the core of the system)
- Speech-to-text: **Whistle** — https://huggingface.co/Cactus-Compute/whistle (16.9 MB, CPU, Apache-2.0; en/de/fr/es/it/nl/pl).
- LLM / tool router: **Needle 3** — https://huggingface.co/Cactus-Compute/needle3 and https://github.com/cactus-compute/needle.
- Install: `pip install "cactus-needle[mic]"`, then `import needle`. Do **not** use `cactus-compute` / `import cactus` (a different API shown on one model card; see the discrepancy note in `docs/03_TECH_STACK.md`).
- Set `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1` before importing `needle`.

## 3. Working agreement (non-negotiable)
1. **Never invent an API.** Before using any `needle` call, check it against the installed package (`inspect.signature`, `help()`), the README, and the real return value. Paste the evidence in the milestone report.
2. **Build in milestones M0→M5** (PRD). After each milestone: run its acceptance proof from `docs/08`, write a report (what ran, raw output trimmed, passed, NOT tested, open questions), then **stop and wait for my go-ahead**.
3. **No "should work."** Anything you claim works must be backed by a command I can run. Say plainly what you could not verify.
4. **Small, reviewable commits**; one concern per change. Don't rewrite a module to fix a bug until you've stated and checked the cause.
5. **No new dependencies or frameworks without a stated need.** P0 uses only: `cactus-needle[mic]`, `pynput` (pending spike S4), `pytest`, and the standard library.
6. **Security rules in `docs/06` are hard constraints**: no `shell=True`, allowlisted apps only, confined file search, T2 tools not implemented, no network calls in runtime code, no audio retained by default, hotkey listener reacts only to the configured combo.
7. Windows 11 is the target. Use `pathlib`; no bash-only scripts.
8. When a fact is uncertain, label it: **verified / supported by evidence / hypothesis needing a test / unknown.**

## 4. Milestones

**M0 — Environment and spikes.** Create the repo skeleton from `docs/02` (src layout, `pyproject.toml`, empty packages, pytest config). Run `scripts/setup.ps1` / `scripts/verify_env.py` (I will run it on my machine if you cannot download models; tell me exactly what you need). Write `docs/SPIKES.md` with raw outputs:
- S1: confirm the package/API (`needle` vs `cactus`) and the installed version.
- S2: real return shapes of `Needle.run()` and `Needle.complete()`; does `complete()` return `function_calls` **without executing** the decorated function? Where is `confidence`? What do `stateless=True` and `reset()` do?
- S3: `needle.transcribe` input formats (path vs numpy array; dtype/rate) and what the result dict contains; behaviour on silence.
- S4: hotkey listener (`pynput`) press/release detection on Windows without recording other keys.
- Stop. Report.

**M1 — Core pipeline, text in.** Protocols (`asr/base.py`, `nlu/base.py`), `NeedleRouter`, `PolicyGate`, `ToolRegistry`, `EventBus`, state machine, CLI `python -m voicecore --text "..."`. Use fakes in unit tests. One stub tool first. Acceptance per `docs/08` M1.

**M2 — Mic + Whistle.** Push-to-talk capture (16 kHz mono, 30 s cap), `WhistleASR`, `--mic` mode. Add `keywords` support from config. Acceptance: speak "open notepad" → transcript printed; repeat with network disabled. Include negative tests: silence, music clip, keyboard noise.

**M3 — Real tools + gate.** Implement `open_app`, `set_reminder`, `search_files` exactly per `docs/04`, one at a time, each with unit + safety tests and eval cases before moving to the next. Reminders persist and fire a `reminder_due` event.

**M4 — Evaluation.** Build `tests/eval/intents.jsonl` (≥30 cases including negatives, multi-action, near-misses) and ask me to record `tests/eval/audio/` samples. Produce `docs/EVAL_REPORT.md`: accuracy, false-action rate, p50/p95 latency per stage on my machine, and evidence-based threshold calibration. Resolve PRD open decision #2 (reminder time format) from the data.

**M5 — Plugin API.** Implement the Level-1 Python surface in `docs/07`, a 20-line sample host script, and a decision note on whether Level-2 (WebSocket) is needed. Tag `v0.1.0`.

## 5. Definition of done (P0)
`pytest -q` green · `scripts/verify_env.py` all PASS · hold hotkey + say "open notepad" works online and offline · negatives trigger zero actions · `docs/EVAL_REPORT.md` exists with real numbers · sample plugin host works · all spec deviations recorded in `docs/DECISIONS.md`.

Start with M0. Do not begin M1 until I approve your M0 report.
