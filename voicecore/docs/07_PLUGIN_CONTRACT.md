# 07 — Plugin contract (how other projects use VoiceCore)

Status: **proposed** — finalise in M5 after the core pipeline is measured. Keep the surface small; semantic-version it from the first release.

## Level 1 — Python library (M5a)
```python
from voicecore import VoiceAssistant, tool

@tool(tier="T1")
def start_focus_mode(minutes: int):
    "Start a focus timer for a number of minutes."
    ...

va = VoiceAssistant.from_config("voicecore.toml")   # loads Whistle + Needle once
va.register(start_focus_mode)
va.on("transcript", lambda e: print(e.text))
va.on("confirm_request", lambda e: e.respond(True))
va.run_text("start a focus session for 25 minutes")  # no mic, for tests
va.run_push_to_talk()                                # blocking; or va.start()/va.stop()
```
Guarantees: host tools go through the **same** gate, tiers and event stream as built-ins; the host cannot bypass the gate except by explicitly subclassing `PolicyGate` (documented as unsafe).

## Level 2 — Local WebSocket sidecar (M5b, only if a non-Python host needs it)
For Tauri/Electron/other-language projects: `python -m voicecore --serve --port 8765`, bound to **127.0.0.1 only**, with a random per-launch token passed by the host.
Messages are JSON `{ "v": 1, "type": ..., ... }`:
- host → core: `register_tools{tools[schema]}`, `start_listening`, `stop_listening`, `text{value}`, `confirm_response{run_id,approved}`
- core → host: every event in 05, plus `tool_call_request{run_id,call}` for tools implemented **in the host** (core sends the call, host returns `tool_result`).
Host-implemented tools keep their tier; the core still applies the gate before sending the request.

## Non-goals for the plugin
No UI, no TTS, no memory/RAG, no cloud. Those belong to the host project.

## Compatibility rules
- Event names and fields in 05 are public API once released.
- Tool schema export format (04) is public API.
- Needle/Whistle are wrapped behind the `ASR` and `Router` protocols so a host can swap them.
