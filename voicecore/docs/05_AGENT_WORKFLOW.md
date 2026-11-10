# 05 — Runtime workflow & state machine

## States
`IDLE → LISTENING → TRANSCRIBING → ROUTING → GATING → (EXECUTING | CONFIRMING | REFUSING) → REPORTING → IDLE`, plus `ERROR → IDLE`.

| State | Entry | Exit | Notes |
|-------|-------|------|-------|
| IDLE | startup / done | hotkey down | models already loaded |
| LISTENING | hotkey down | hotkey up or 30 s cap | events: `listening_started` |
| TRANSCRIBING | audio captured | transcript | empty/whitespace → IDLE, event `no_speech` |
| ROUTING | transcript | RouteResult | 0 calls → REPORTING("nothing to do") |
| GATING | per call, in order | decision | uses tier + confidence (06) |
| CONFIRMING | decision=CONFIRM | user yes/no or 10 s timeout | timeout = no. P0 confirm is keyboard (`y`/`n`) not voice |
| EXECUTING | decision=ACT or confirmed | tool result | per-tool timeout; result recorded |
| REFUSING | decision=REFUSE | — | report reason; no side effects |
| REPORTING | all calls done | — | console line + `done` event |

## Rules
- Multi-call utterances run **in order**; stop the chain at the first REFUSE or failed call and report what did and didn't run.
- A new hotkey press during a non-IDLE state is ignored (P0) — no barge-in.
- One pipeline run = one correlation id attached to every event.
- Models are loaded once; a crash in a tool must not unload them.
- Needle conversation state: P0 treats each utterance independently (`stateless=True` if S2 confirms its meaning, otherwise `reset()` after each run). Multi-turn context is a later decision.

## Events (all carry `run_id`, `ts`)
`listening_started`, `listening_stopped`, `no_speech`, `transcript{text,language,asr_ms}`, `route{calls[],confidence,nlu_ms}`, `gate{call,decision,reason}`, `confirm_request{call}`, `tool_result{call,result,ms}`, `reminder_due{...}`, `error{stage,type,message}`, `done{total_ms}`.
