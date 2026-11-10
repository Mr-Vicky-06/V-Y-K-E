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


def test_gate_precheck_rejection_independent_of_high_confidence():
    """A failed tool precheck must immediately REFUSE, even if confidence is 1.0."""
    reg = ToolRegistry()

    def checked_tool(item: str):
        return {"item": item}

    def my_precheck(args):
        if args.get("item") != "valid":
            return False, "Only 'valid' item is permitted"
        return True, ""

    reg.register(checked_tool, tier="T1", name="checked_tool", precheck=my_precheck)
    gate = PolicyGate(config=PolicyConfig(act_threshold=0.80), registry=reg)

    # 1. Invalid argument with 1.0 confidence -> must REFUSE
    bad_call = ToolCall(name="checked_tool", arguments={"item": "malicious"})
    dec = gate.decide(bad_call, confidence=1.0)
    assert dec.decision == Decision.REFUSE
    assert "Pre-check failed" in dec.reason
    assert "Only 'valid' item is permitted" in dec.reason

    # 2. Valid argument with 1.0 confidence -> must ACT
    good_call = ToolCall(name="checked_tool", arguments={"item": "valid"})
    dec_good = gate.decide(good_call, confidence=1.0)
    assert dec_good.decision == Decision.ACT


def test_open_app_precheck_in_gate():
    from voicecore.tools.builtin.open_app import open_app, open_app_precheck
    reg = ToolRegistry()
    reg.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck)
    gate = PolicyGate(config=PolicyConfig(act_threshold=0.80), registry=reg)

    # Allowlisted app with confidence 0.90 -> ACT
    call_ok = ToolCall(name="open_app", arguments={"app_name": "notepad"})
    assert gate.decide(call_ok, confidence=0.90).decision == Decision.ACT

    # Non-allowlisted app with confidence 0.99 -> REFUSE
    call_bad = ToolCall(name="open_app", arguments={"app_name": "the quarterly report"})
    dec_bad = gate.decide(call_bad, confidence=0.99)
    assert dec_bad.decision == Decision.REFUSE
    assert "Pre-check failed" in dec_bad.reason
    assert "is not an allowed app" in dec_bad.reason


def test_search_files_precheck_in_gate():
    from voicecore.tools.builtin.search_files import search_files, search_files_precheck
    reg = ToolRegistry()
    # Force empty roots
    reg.register(
        search_files,
        tier="T0",
        name="search_files",
        precheck=lambda args: search_files_precheck(args, roots=[]),
    )
    gate = PolicyGate(config=PolicyConfig(act_threshold=0.80), registry=reg)

    call = ToolCall(name="search_files", arguments={"query": "report"})
    dec = gate.decide(call, confidence=0.99)
    assert dec.decision == Decision.REFUSE
    assert "Pre-check failed" in dec.reason
    assert "No search root directories configured" in dec.reason


def test_set_reminder_precheck_in_gate():
    from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
    reg = ToolRegistry()
    reg.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck)
    gate = PolicyGate(config=PolicyConfig(act_threshold=0.80), registry=reg)

    # Past time with 0.95 confidence -> REFUSE
    call_past = ToolCall(name="set_reminder", arguments={"message": "old meeting", "when": "2020-01-01T10:00:00"})
    dec = gate.decide(call_past, confidence=0.95)
    assert dec.decision == Decision.REFUSE
    assert "Pre-check failed" in dec.reason
    assert "past" in dec.reason

