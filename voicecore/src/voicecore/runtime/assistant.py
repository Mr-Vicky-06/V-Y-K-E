"""VoiceCore runtime assistant and state machine."""
from __future__ import annotations

import enum
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from voicecore.asr.base import ASR, Transcript
from voicecore.config import VoiceCoreConfig
from voicecore.events import (
    ConfirmRequestEvent,
    DoneEvent,
    ErrorEvent,
    EventBus,
    GateEvent,
    ListeningStartedEvent,
    ListeningStoppedEvent,
    NoSpeechEvent,
    RouteEvent,
    ToolResultEvent,
    TranscriptEvent,
)
from voicecore.nlu.base import RouteResult, Router, ToolCall
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.tools.registry import ToolRegistry


class State(str, enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    ROUTING = "ROUTING"
    GATING = "GATING"
    EXECUTING = "EXECUTING"
    CONFIRMING = "CONFIRMING"
    REFUSING = "REFUSING"
    REPORTING = "REPORTING"
    ERROR = "ERROR"


class Assistant:
    """Core runtime assistant coordinating ASR, NLU router, Policy Gate, and Tool Registry."""

    def __init__(
        self,
        router: Router,
        registry: ToolRegistry,
        policy_gate: PolicyGate,
        asr: Optional[ASR] = None,
        config: Optional[VoiceCoreConfig] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.router = router
        self.registry = registry
        self.policy_gate = policy_gate
        self.asr = asr
        self.config = config or VoiceCoreConfig()
        self.event_bus = event_bus or EventBus()
        self._state = State.IDLE
        self._state_lock = threading.RLock()

        # Push-to-talk runtime state
        self._active_run_id: Optional[str] = None
        self._press_time: float = 0.0

    @property
    def state(self) -> State:
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, new_state: State) -> None:
        with self._state_lock:
            self._state = new_state

    def run_audio(
        self,
        audio_data: Any,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the pipeline from speech audio (ASR -> Router -> Gate -> Executor)."""
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        try:
            # 1. TRANSCRIBING stage
            self.state = State.TRANSCRIBING
            if self.asr is None:
                raise RuntimeError("No ASR engine configured in Assistant for speech input")

            transcript: Transcript = self.asr.transcribe(audio_data)

            # Check for silence or empty transcript
            if not transcript.text or not transcript.text.strip():
                self.event_bus.publish(NoSpeechEvent(run_id=run_id))
                self.state = State.IDLE
                return []

            # Emit TranscriptEvent
            self.event_bus.publish(
                TranscriptEvent(
                    run_id=run_id,
                    text=transcript.text,
                    language=transcript.language,
                    asr_ms=transcript.asr_ms,
                )
            )

            # Delegate to text pipeline
            return self._run_pipeline_from_text(
                text=transcript.text,
                run_id=run_id,
                t_start=t_start,
                confirmer=confirmer,
            )

        except Exception as e:
            self.state = State.ERROR
            self.event_bus.publish(
                ErrorEvent(
                    run_id=run_id,
                    stage=str(self.state),
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )
            self.state = State.IDLE
            raise

    def run_text(
        self,
        text: str,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the core pipeline from text input (bypassing mic/ASR)."""
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        try:
            cleaned_text = (text or "").strip()
            if not cleaned_text:
                self.event_bus.publish(NoSpeechEvent(run_id=run_id))
                self.state = State.IDLE
                return []

            return self._run_pipeline_from_text(
                text=cleaned_text,
                run_id=run_id,
                t_start=t_start,
                confirmer=confirmer,
            )

        except Exception as e:
            self.state = State.ERROR
            self.event_bus.publish(
                ErrorEvent(
                    run_id=run_id,
                    stage=str(self.state),
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )
            self.state = State.IDLE
            raise

    def _run_pipeline_from_text(
        self,
        text: str,
        run_id: str,
        t_start: float,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Common routing, gating, and execution pipeline."""
        results: List[Dict[str, Any]] = []

        # 1. ROUTING stage
        self.state = State.ROUTING
        route_res: RouteResult = self.router.route(text)

        self.event_bus.publish(
            RouteEvent(
                run_id=run_id,
                calls=[{"name": c.name, "arguments": c.arguments} for c in route_res.calls],
                confidence=route_res.confidence,
                nlu_ms=route_res.nlu_ms,
                reasoning=route_res.reasoning,
                negation=route_res.negation,
                ungrounded=route_res.ungrounded,
            )
        )

        if not route_res.calls:
            self.state = State.REPORTING
            total_ms = (time.perf_counter() - t_start) * 1000.0
            self.event_bus.publish(DoneEvent(run_id=run_id, total_ms=total_ms))
            self.state = State.IDLE
            return []

        # 2. GATING & EXECUTION stage for each call in order
        for call in route_res.calls:
            self.state = State.GATING
            decision = self.policy_gate.decide(
                call=call,
                confidence=route_res.confidence,
                negation=route_res.negation,
                ungrounded=route_res.ungrounded,
            )

            call_dict = {"name": call.name, "arguments": call.arguments}
            self.event_bus.publish(
                GateEvent(
                    run_id=run_id,
                    call=call_dict,
                    decision=decision.decision,
                    reason=decision.reason,
                )
            )

            # Action evaluation
            if decision.decision == Decision.REFUSE:
                self.state = State.REFUSING
                results.append({
                    "call": call_dict,
                    "status": "refused",
                    "reason": decision.reason,
                })
                # Rule: Stop multi-call chain at first refusal
                break

            elif decision.decision == Decision.CONFIRM:
                self.state = State.CONFIRMING
                self.event_bus.publish(ConfirmRequestEvent(run_id=run_id, call=call_dict))
                confirmed = False
                if confirmer:
                    confirmed = confirmer(call)

                if not confirmed:
                    results.append({
                        "call": call_dict,
                        "status": "refused",
                        "reason": "Confirmation denied or timed out",
                    })
                    break

            # EXECUTING
            self.state = State.EXECUTING
            t_exec = time.perf_counter()
            tool_res = self.registry.execute(call.name, call.arguments)
            exec_ms = (time.perf_counter() - t_exec) * 1000.0

            self.event_bus.publish(
                ToolResultEvent(
                    run_id=run_id,
                    call=call_dict,
                    result=tool_res,
                    ms=exec_ms,
                )
            )

            results.append({
                "call": call_dict,
                "status": "executed" if tool_res.get("ok") else "failed",
                "result": tool_res,
                "ms": exec_ms,
            })

            if not tool_res.get("ok"):
                # Stop chain on tool failure
                break

        # 3. REPORTING stage
        self.state = State.REPORTING
        total_ms = (time.perf_counter() - t_start) * 1000.0
        self.event_bus.publish(DoneEvent(run_id=run_id, total_ms=total_ms))
        self.state = State.IDLE
        return results
