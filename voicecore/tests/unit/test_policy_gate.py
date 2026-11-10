import pytest
from voicecore.config import PolicyConfig
from voicecore.nlu.base import ToolCall
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    reg = ToolRegistry()

    def read_tool(query: str):
        """Read only."""
        return {"q": query}

    def write_tool(msg: str):
        """Reversible write."""
        return {"m": msg}

    def dangerous_tool(cmd: str):
        """Privileged tool."""
        return {"cmd": cmd}

    reg.register(read_tool, tier="T0", name="read_tool")
    reg.register(write_tool, tier="T1", name="write_tool")
    reg.register(dangerous_tool, tier="T2", name="dangerous_tool")
    return reg


@pytest.fixture
def gate(registry):
    cfg = PolicyConfig(act_threshold=0.80, confirm_threshold=0.50)
    return PolicyGate(config=cfg, registry=registry)


def test_gate_act_high_confidence_t0_and_t1(gate):
    call_t0 = ToolCall(name="read_tool", arguments={"query": "test"})
    call_t1 = ToolCall(name="write_tool", arguments={"msg": "hello"})

    dec_t0 = gate.decide(call_t0, confidence=0.85)
    assert dec_t0.decision == Decision.ACT

    dec_t1 = gate.decide(call_t1, confidence=0.80)
    assert dec_t1.decision == Decision.ACT


def test_gate_confirm_medium_confidence(gate):
    call_t0 = ToolCall(name="read_tool", arguments={"query": "test"})
    call_t1 = ToolCall(name="write_tool", arguments={"msg": "hello"})

    dec_t0 = gate.decide(call_t0, confidence=0.65)
    assert dec_t0.decision == Decision.CONFIRM

    dec_t1 = gate.decide(call_t1, confidence=0.50)
    assert dec_t1.decision == Decision.CONFIRM


def test_gate_refuse_low_confidence(gate):
    call = ToolCall(name="write_tool", arguments={"msg": "hello"})
    dec = gate.decide(call, confidence=0.49)
    assert dec.decision == Decision.REFUSE
    assert "below confirm threshold" in dec.reason


def test_gate_refuse_t2_in_p0(gate):
    call = ToolCall(name="dangerous_tool", arguments={"cmd": "reboot"})
    dec = gate.decide(call, confidence=0.99)
    assert dec.decision == Decision.REFUSE
    assert "forbidden in P0" in dec.reason


def test_gate_refuse_unknown_tool(gate):
    call = ToolCall(name="unregistered_tool", arguments={})
    dec = gate.decide(call, confidence=0.99)
    assert dec.decision == Decision.REFUSE
    assert "not in the authorized registry" in dec.reason


def test_gate_refuse_on_negation(gate):
    call = ToolCall(name="write_tool", arguments={"msg": "hello"})
    dec = gate.decide(call, confidence=0.95, negation=True)
    assert dec.decision == Decision.REFUSE
    assert "Negation detected" in dec.reason


def test_gate_refuse_on_ungrounded_arguments(gate):
    call = ToolCall(name="write_tool", arguments={"msg": "hello"})
    dec = gate.decide(call, confidence=0.95, ungrounded=["write_tool.msg"])
    assert dec.decision == Decision.REFUSE
    assert "Ungrounded arguments detected" in dec.reason

