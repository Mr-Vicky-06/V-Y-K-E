"""Unit tests for the M5 Plugin API (VoiceAssistant, @tool decorator, host tool safety)."""
import pytest
from unittest.mock import MagicMock

from voicecore import VoiceAssistant, tool
from voicecore.config import VoiceCoreConfig, PolicyConfig
from voicecore.events import (
    ConfirmRequestEvent,
    DoneEvent,
    GateEvent,
    RouteEvent,
    TranscriptEvent,
)
from voicecore.nlu.base import RouteResult, ToolCall
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.registry import ToolRegistry


class FakeRouter:
    """Mock router returning predefined RouteResult."""
    def __init__(self, result: RouteResult):
        self._result = result

    def route(self, text: str) -> RouteResult:
        return self._result


def test_tool_decorator_attributes():
    """Verify @tool decorator attaches metadata correctly."""
    def sample_precheck(args):
        return True, "OK"

    @tool(tier="T0", precheck=sample_precheck, triggers=["find", "locate"], name="custom_find")
    def find_doc(query: str):
        """Search query."""
        return {"query": query}

    assert getattr(find_doc, "_voicecore_tier") == "T0"
    assert getattr(find_doc, "_voicecore_precheck") is sample_precheck
    assert getattr(find_doc, "_voicecore_triggers") == ["find", "locate"]
    assert getattr(find_doc, "_voicecore_name") == "custom_find"
    assert getattr(find_doc, "_voicecore_is_host") is True

    # Bare @tool decorator
    @tool
    def bare_func():
        """No args."""
        return {}

    assert getattr(bare_func, "_voicecore_tier") is None
    assert getattr(bare_func, "_voicecore_precheck") is None
    assert getattr(bare_func, "_voicecore_is_host") is True


def test_host_tool_without_precheck_always_confirms():
    """Rule: Host-provided tools default to always-CONFIRM unless they supply precheck and tier."""
    config = VoiceCoreConfig(policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50))
    va = VoiceAssistant.from_config(config, load_builtins=False)

    @tool(tier="T1")
    def host_action(val: str):
        """Host action without precheck."""
        return {"val": val}

    td = va.register(host_action)
    assert td.is_host is True
    assert td.precheck is None

    # Evaluate via PolicyGate with high confidence (0.95 > 0.80)
    call = ToolCall(name="host_action", arguments={"val": "test"})
    dec = va.policy_gate.decide(call, confidence=0.95)

    # Must be CONFIRM, never ACT!
    assert dec.decision == Decision.CONFIRM
    assert "always-CONFIRM" in dec.reason


def test_host_tool_without_explicit_tier_always_confirms():
    """Rule: Host-provided tools without explicit tier default to always-CONFIRM even with precheck."""
    config = VoiceCoreConfig(policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50))
    va = VoiceAssistant.from_config(config, load_builtins=False)

    def my_check(args):
        return True, "OK"

    @tool(precheck=my_check)
    def host_action2(val: str):
        """Host action with precheck but no tier."""
        return {"val": val}

    td = va.register(host_action2)
    assert td.is_host is True
    assert td.has_explicit_tier is False
    assert td.tier == "T1"  # Defaulted to T1

    call = ToolCall(name="host_action2", arguments={"val": "test"})
    dec = va.policy_gate.decide(call, confidence=0.95)

    # Must be CONFIRM because host did not explicitly provide a tier
    assert dec.decision == Decision.CONFIRM
    assert "always-CONFIRM" in dec.reason


def test_host_tool_with_precheck_and_tier_can_act():
    """Rule: Host tool with both explicit tier and precheck can ACT if confidence >= act_threshold."""
    config = VoiceCoreConfig(policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50))
    va = VoiceAssistant.from_config(config, load_builtins=False)

    def valid_precheck(args):
        if args.get("val") == "bad":
            return False, "Bad value"
        return True, "Valid"

    @tool(tier="T1", precheck=valid_precheck, triggers=["action"])
    def safe_host_action(val: str):
        """Full compliance tool."""
        return {"val": val}

    va.register(safe_host_action)

    # 1. High confidence + passing precheck -> ACT
    call_ok = ToolCall(name="safe_host_action", arguments={"val": "good"})
    dec_ok = va.policy_gate.decide(call_ok, confidence=0.85)
    assert dec_ok.decision == Decision.ACT

    # 2. Medium confidence + passing precheck -> CONFIRM
    dec_mid = va.policy_gate.decide(call_ok, confidence=0.65)
    assert dec_mid.decision == Decision.CONFIRM

    # 3. Failing precheck -> REFUSE (regardless of confidence)
    call_bad = ToolCall(name="safe_host_action", arguments={"val": "bad"})
    dec_bad = va.policy_gate.decide(call_bad, confidence=0.99)
    assert dec_bad.decision == Decision.REFUSE
    assert "Pre-check failed: Bad value" in dec_bad.reason


def test_host_event_listeners():
    """Verify va.on(...) registers handlers and receives events."""
    config = VoiceCoreConfig()
    va = VoiceAssistant.from_config(config, load_builtins=False)

    received_transcripts = []
    va.on("transcript", lambda e: received_transcripts.append(e.text))

    va.event_bus.publish(TranscriptEvent(run_id="test_run", text="hello world"))
    assert received_transcripts == ["hello world"]

    # Unknown event name raises ValueError
    with pytest.raises(ValueError, match="Unknown event name"):
        va.on("unknown_event_type", lambda e: None)


def test_host_confirm_request_respond():
    """Verify host can respond to confirmation requests via event listener."""
    config = VoiceCoreConfig(policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50))
    va = VoiceAssistant.from_config(config, load_builtins=False)

    executed = []

    @tool(tier="T1")
    def confirmable_action(val: str):
        executed.append(val)
        return {"status": "ok"}

    va.register(confirmable_action)

    # Configure FakeRouter to return route result for confirmable_action
    route_res = RouteResult(
        calls=[ToolCall(name="confirmable_action", arguments={"val": "test_val"})],
        confidence=0.85,
    )
    va.assistant.router = FakeRouter(route_res)

    # 1. Confirm listener approves the call
    va.on("confirm_request", lambda e: e.respond(True))

    results = va.run_text("trigger action")
    assert len(results) == 1
    assert results[0]["status"] == "executed"
    assert executed == ["test_val"]

    # 2. Confirm listener denies the call
    executed.clear()
    va = VoiceAssistant.from_config(config, load_builtins=False)
    va.register(confirmable_action)
    va.assistant.router = FakeRouter(route_res)
    va.on("confirm_request", lambda e: e.respond(False))

    results_denied = va.run_text("trigger action")
    assert len(results_denied) == 1
    assert results_denied[0]["status"] == "refused"
    assert executed == []
