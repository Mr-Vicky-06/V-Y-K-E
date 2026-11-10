from typing import Any, Dict, List, Optional
import pytest

from voicecore.config import VoiceCoreConfig, PolicyConfig
from voicecore.events import (
    DoneEvent,
    ErrorEvent,
    EventBus,
    GateEvent,
    NoSpeechEvent,
    RouteEvent,
    ToolResultEvent,
)
from voicecore.nlu.base import RouteResult, Router, ToolCall
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant, State
from voicecore.tools.registry import ToolRegistry


class FakeRouter(Router):
    def __init__(self, result: Optional[RouteResult] = None):
        self.result = result or RouteResult()
        self.queries_received: List[str] = []

    def route(self, text: str) -> RouteResult:
        self.queries_received.append(text)
        return self.result


@pytest.fixture
def test_setup():
    registry = ToolRegistry()
    execution_log = []

    def dummy_app(app_name: str) -> dict:
        execution_log.append(("dummy_app", app_name))
        return {"ok": True, "app_name": app_name}

    def failing_tool() -> dict:
        execution_log.append(("failing_tool",))
        return {"ok": False, "error": "device_error"}

    registry.register(dummy_app, tier="T1", name="dummy_app")
    registry.register(failing_tool, tier="T1", name="failing_tool")

    config = VoiceCoreConfig(
        policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50)
    )
    gate = PolicyGate(config=config.policy, registry=registry)
    event_bus = EventBus()

    events_seen = []
    event_bus.subscribe_all(lambda e: events_seen.append(e))

    return registry, gate, config, event_bus, execution_log, events_seen


def test_assistant_run_text_direct_act(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup

    route_res = RouteResult(
        calls=[ToolCall(name="dummy_app", arguments={"app_name": "notepad"})],
        confidence=0.90,
        nlu_ms=10.0,
        reasoning="direct command",
    )
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    results = assistant.run_text("open notepad")

    assert assistant.state == State.IDLE
    assert len(results) == 1
    assert results[0]["status"] == "executed"
    assert ("dummy_app", "notepad") in execution_log

    # Verify event types published
    types = [type(e) for e in events_seen]
    assert RouteEvent in types
    assert GateEvent in types
    assert ToolResultEvent in types
    assert DoneEvent in types


def test_assistant_run_text_empty_input(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    router = FakeRouter()
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    results = assistant.run_text("   ")

    assert assistant.state == State.IDLE
    assert len(results) == 0
    assert len(execution_log) == 0
    assert any(isinstance(e, NoSpeechEvent) for e in events_seen)


def test_assistant_run_text_zero_calls(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    route_res = RouteResult(calls=[], confidence=0.95, reasoning="small talk")
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    results = assistant.run_text("what is the weather?")

    assert assistant.state == State.IDLE
    assert len(results) == 0
    assert len(execution_log) == 0
    assert any(isinstance(e, RouteEvent) for e in events_seen)
    assert any(isinstance(e, DoneEvent) for e in events_seen)


def test_assistant_confirm_accepted(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    route_res = RouteResult(
        calls=[ToolCall(name="dummy_app", arguments={"app_name": "calc"})],
        confidence=0.65,  # Medium confidence -> CONFIRM
    )
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    # Confirmer approves
    results = assistant.run_text("open calc", confirmer=lambda call: True)

    assert len(results) == 1
    assert results[0]["status"] == "executed"
    assert ("dummy_app", "calc") in execution_log


def test_assistant_confirm_denied(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    route_res = RouteResult(
        calls=[ToolCall(name="dummy_app", arguments={"app_name": "calc"})],
        confidence=0.65,
    )
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    # Confirmer denies
    results = assistant.run_text("open calc", confirmer=lambda call: False)

    assert len(results) == 1
    assert results[0]["status"] == "refused"
    assert len(execution_log) == 0


def test_assistant_multi_call_stops_on_refusal(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    route_res = RouteResult(
        calls=[
            ToolCall(name="dummy_app", arguments={"app_name": "notepad"}),
            ToolCall(name="unknown_tool", arguments={}),
        ],
        confidence=0.85,
    )
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    results = assistant.run_text("open notepad and do secret thing")

    assert len(results) == 2
    assert results[0]["status"] == "executed"
    assert results[1]["status"] == "refused"
    assert len(execution_log) == 1


def test_assistant_multi_call_stops_on_tool_failure(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup
    route_res = RouteResult(
        calls=[
            ToolCall(name="failing_tool", arguments={}),
            ToolCall(name="dummy_app", arguments={"app_name": "notepad"}),
        ],
        confidence=0.90,
    )
    router = FakeRouter(result=route_res)
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    results = assistant.run_text("fail and then open notepad")

    assert len(results) == 1
    assert results[0]["status"] == "failed"
    # Second tool must not have been executed
    assert len(execution_log) == 1
    assert execution_log[0][0] == "failing_tool"


def test_assistant_router_crash_recovers_to_idle(test_setup):
    registry, gate, config, event_bus, execution_log, events_seen = test_setup

    class ExplodingRouter(Router):
        def route(self, text: str) -> RouteResult:
            raise ValueError("Corrupt weights")

    assistant = Assistant(router=ExplodingRouter(), registry=registry, policy_gate=gate, config=config, event_bus=event_bus)

    with pytest.raises(ValueError, match="Corrupt weights"):
        assistant.run_text("crash me")

    assert assistant.state == State.IDLE
    assert any(isinstance(e, ErrorEvent) for e in events_seen)
