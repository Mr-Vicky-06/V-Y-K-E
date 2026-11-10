# 08 — Testing & verification protocol

Principle: **"it works" is never a claim without a command that proves it.** Each milestone lists its proof.

## Layers
1. **Unit (fast, no models):** gate decisions, registry validation, path confinement, allowlist, reminder parsing/persistence, state machine transitions — using fake ASR/Router.
2. **Contract tests on the real package:** `scripts/verify_env.py` — imports `needle`, loads Whistle and Needle, runs a silence clip (expect empty text) and a dummy tool call.
3. **Eval sets (real models):**
   - `tests/eval/intents.jsonl` — ≥30 cases `{utterance, expected_calls[]}`: single action, two actions in order, paraphrases, accent-free English variants, **no-tool cases** (small talk, unsupported requests), near-miss names (e.g., "open notes").
   - `tests/eval/audio/` — ≥20 short WAVs recorded by Vignesh with transcripts (include background noise, fast speech, a music clip, silence).
   Report: transcript accuracy (word error rate by hand or a small script), tool-name accuracy, argument exact-match, false-action rate on negatives, p50/p95 latency per stage.
4. **Offline proof:** disable the network adapter (or use a firewall rule), run M2 acceptance again. Pass = identical behaviour.
5. **Safety tests:** unknown tool name refused; `open_app("powershell")` refused (not allowlisted); `search_files` with `..\\` or a symlink outside roots refused; no network sockets opened during a run; hotkey listener ignores other keys.

## Acceptance by milestone
| Milestone | Proof (command → expected) |
|-----------|----------------------------|
| M0 | `scripts/verify_env.py` → all steps PASS; spike notes S1–S4 written to `docs/SPIKES.md` with raw outputs |
| M1 | `python -m voicecore --text "open notepad"` → route event + gate decision + tool_result; `pytest -q` green |
| M2 | Hold hotkey, say "open notepad" → transcript printed, Notepad opens; same with network off |
| M3 | All three tools pass unit + safety tests; negatives cause zero executions |
| M4 | `docs/EVAL_REPORT.md` with numbers, thresholds calibrated with evidence, latency table |
| M5 | A 20-line sample host script registers a custom tool and receives events; version tag v0.1.0 |

## Debugging protocol
When something fails: write observed vs expected, capture the raw return value of the failing stage, isolate the stage with a fake for its neighbours, change one thing, re-run the same command. Do not rewrite a module to "fix" a bug before the cause is stated and checked.

## Reporting rule
Every milestone report lists: what was run, raw output (trimmed), what passed, what was **not** tested, and open questions. No "should work".
