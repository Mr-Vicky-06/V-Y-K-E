"""VoiceCore runtime assistant and state machine."""
from __future__ import annotations

import enum
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

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
        self.state = State.IDLE

    def run_text(
        self,
        text: str,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the core pipeline from text input (bypassing mic/ASR).
        
        State transitions:
        IDLE -> ROUTING -> GATING -> (EXECUTING | CONFIRMING | REFUSING) -> REPORTING -> IDLE
        """
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()
        results: List[Dict[str, Any]] = []

        try:
            # 1. Check for empty input
            cleaned_text = (text or "").strip()
            if not cleaned_text:
                self.event_bus.publish(NoSpeechEvent(run_id=run_id))
                self.state = State.IDLE
                return []

            # 2. ROUTING stage
            self.state = State.ROUTING
            route_res: RouteResult = self.router.route(cleaned_text)

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

            # 3. GATING & EXECUTION stage for each call in order
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

            # 4. REPORTING stage
            self.state = State.REPORTING
            total_ms = (time.perf_counter() - t_start) * 1000.0
            self.event_bus.publish(DoneEvent(run_id=run_id, total_ms=total_ms))
            self.state = State.IDLE
            return results

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

