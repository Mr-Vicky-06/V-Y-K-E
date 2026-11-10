# 01 — PRD: VoiceCore (offline voice-control foundation)

## Purpose
A reusable, fully on-device voice layer: **speech → text (Whistle) → tool calls (Needle 3) → safe execution**.
It is (a) the first prototype of a complete PC/phone system-automation assistant and (b) a plugin other voice projects (Web-Buddy, Spider Buddy, ORION PAX, etc.) can embed instead of re-solving ASR + intent routing.

## Users
- Primary: Vignesh, on Windows, English speech.
- Secondary: other projects of his that need "voice in → action out" through a stable API.

## Goals (prototype = P0)
1. Hold a hotkey, speak, release → transcript → tool call → action, with no network after first-time model download.
2. Three real actions: **open an app**, **set a reminder**, **search local files**.
3. A safety gate between "model said X" and "computer did X" (risk tiers + Needle confidence).
4. A clean plugin surface (Python API first; local WebSocket later) so another project can register its own tools.
5. Everything measurable: every claim of "it works" has a test or a script (see 08).

## Non-goals (P0)
- Wake word / always-on mic (Whistle can emit text from music/noise; push-to-talk avoids this).
- TTS / spoken replies. Text/console feedback only.
- Phone app (Phase 3 — see 02 §Phone path).
- Tamil or mixed Tamil-English speech (Whistle's documented languages: en, de, fr, es, it, nl, pl).
- Shell execution, file deletion, sending messages, payments (tier T2 — forbidden in P0).
- Cloud LLMs of any kind.

## Functional requirements
| ID | Requirement |
|----|-------------|
| F1 | Push-to-talk capture, 16 kHz mono, max 30 s per utterance (Whistle single-pass window). |
| F2 | Transcribe with Whistle; empty transcript → return to idle silently. |
| F3 | Route transcript with Needle; 0..n ordered tool calls plus confidence. |
| F4 | Policy gate decides ACT / CONFIRM / REFUSE per call. |
| F5 | Execute tools via an explicit registry; unknown tool name → refuse. |
| F6 | Emit structured events for every stage (for UI, logs, plugin consumers). |
| F7 | Config file for hotkey, thresholds, allowlisted apps, searchable folders. |
| F8 | `python -m voicecore --text "open notepad"` runs the same pipeline without a mic (for tests). |

## Success metrics (targets are hypotheses until measured in M4)
- Intent eval set (≥30 cases): tool-name accuracy and argument exact-match reported separately; target ≥90% tool-name, to be revised after the first run.
- End-to-end latency (hotkey release → action started) for ≤5 s utterance: target <2 s on Vignesh's laptop. Unknown until measured.
- Zero tool executions on the negative set (silence, music, off-topic requests).
- Transcription still works with network disabled after setup.

## Milestones
M0 environment + spikes · M1 core pipeline (text in) · M2 mic + Whistle · M3 tools + gate · M4 eval + latency report · M5 plugin API. Stop-and-report after each (see ANTIGRAVITY_PROMPT.md).

## Open decisions (agent must surface, not silently decide)
1. Hotkey library (pynput vs keyboard) — pick after spike S4.
2. Reminder time format: model-produced ISO string vs deterministic parser — decide from eval.
3. Reminder delivery: console + Windows toast? Needs a dependency decision.
4. WebSocket server framework for Phase 2 (stdlib asyncio vs FastAPI).
