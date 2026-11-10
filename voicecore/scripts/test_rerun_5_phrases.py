"""Test re-running the 5 affected reminder phrases without literal examples in docstring."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cactus
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
from voicecore.tools.registry import ToolRegistry
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.config import PolicyConfig

cactus.set_threads(2)

registry = ToolRegistry()
registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=["open", "launch", "start", "run", "calculator", "calc", "notepad"])
registry.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck, triggers=["search", "find", "locate", "files", "lookup"])
registry.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck, triggers=["remind", "reminder", "schedule", "alarm", "timer"])

gate = PolicyGate(config=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50), registry=registry)
router = NeedleRouter(registry=registry, stateless=True)

phrases = [
    "remind me about that stuff",
    "set a reminder",
    "remind me about notepad",
    "remind me of the calculator",
    "remind me to find budget",
    "set a reminder about quarterly report",
]

print("=" * 85)
print(" Re-running 5 Affected Reminder Phrases without Literal Examples in Docstring")
print("=" * 85)

for p in phrases:
    t = p[0].upper() + p[1:] + "."
    res = router.route(t)
    calls_str = ", ".join(f"{c.name}({c.arguments})" for c in res.calls) if res.calls else "NO_CALLS"
    dec = "NO_CALLS"
    reason = "No tool called"
    if res.calls:
        g = gate.decide(res.calls[0], confidence=res.confidence, negation=res.negation, ungrounded=res.ungrounded)
        dec = g.decision
        reason = g.reason

    print(f"Utterance:  \"{p}\"")
    print(f"  Calls:       {calls_str}")
    print(f"  Confidence:  {res.confidence:.4f}")
    print(f"  Ungrounded:  {res.ungrounded}")
    print(f"  Gate:        {dec} ({reason})")
    print("-" * 85)
