# 02 — Architecture

## Pipeline
```
 hotkey down ─► AudioCapture ─► [16 kHz mono buffer]
                                      │ hotkey up
                                      ▼
                              WhistleASR.transcribe()  ── empty? ─► IDLE
                                      │ text
                                      ▼
                              NeedleRouter.route(text) ─► ToolCall[] + confidence
                                      │
                                      ▼
                              PolicyGate.decide(call)  ─► ACT | CONFIRM | REFUSE
                                      │
                   ┌──────────────────┼───────────────────┐
                   ▼                  ▼                   ▼
              Executor.run      Confirmer.ask         Reporter(refused)
                   └──────────────────┴───────────────────┘
                                      ▼
                         EventBus ─► console / UI / plugin clients
```
One process, one worker thread for the pipeline, one capture thread, one hotkey listener thread. Models are loaded once at startup and reused (loading per request is a bug).

## Module layout
```
voicecore/
  pyproject.toml
  config/voicecore.toml, config/apps.allowlist.json
  src/voicecore/
    config.py            # load/validate TOML
    events.py            # Event dataclasses + EventBus (sync, thread-safe)
    audio/capture.py     # push-to-talk recorder (sounddevice via cactus-needle[mic])
    asr/base.py          # ASR protocol: transcribe(audio) -> Transcript
    asr/whistle.py       # wraps needle.Whistle
    nlu/base.py          # Router protocol: route(text) -> RouteResult
    nlu/needle_router.py # wraps needle.Needle (+ confidence extraction)
    policy/gate.py       # risk tiers + confidence thresholds
    tools/registry.py    # explicit register(), schema export, lookup
    tools/builtin/       # open_app.py, set_reminder.py, search_files.py
    runtime/assistant.py # state machine (see 05), wires everything
    plugin/api.py        # public surface for other projects (see 07)
    plugin/server.py     # Phase 2: localhost WebSocket
    __main__.py          # CLI: --text, --mic, --serve
  tests/ scripts/ docs/
```
Rule: `asr/` and `nlu/` define **protocols**; `runtime/` depends only on protocols. Tests inject fakes, and another project can swap in a different ASR or router.

## Phone path (Phase 3, not P0)
Verified from the Needle repo and model cards: the engine ships per-platform folders with a `needle` binary, `libneedle.a` and `needle.h` (C API), and one engine loads both Whistle and Needle `.cact` files. So the phone version is a **port of the runtime**, not of this Python package. What carries over: tool schemas (keep them JSON-exportable — the CLI takes `--tools tools.json`), policy rules, and the eval set. Read Cactus's "supported devices" guide at that time.

## Offline model
- First run needs internet to fetch engine + weights; they are cached afterwards (stated by Whistle's model card).
- Disable telemetry **before** the engine loads: `NEEDLE_TELEMETRY=0`, `DO_NOT_TRACK=1` (README: telemetry is on by default in the binary).
- Offline proof = run the M2 acceptance test with the network disabled (see 08).

## Failure handling
Every stage returns a typed result or raises a typed error; the state machine always returns to IDLE and emits an `error` event. No stage swallows exceptions silently.
