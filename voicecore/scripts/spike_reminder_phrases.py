"""Spike: Introspect how Needle routes set_reminder phrases.

Phrases to test:
  1. "remind me at 6"
  2. "tomorrow at 10"
  3. "in 20 minutes"
  4. "remind me to call mom tomorrow at 10"
  5. "set a reminder to buy milk in 20 minutes"

We record:
  - proposed function_calls (name + arguments)
  - what `when` argument value comes out
  - whether `validation.ungrounded` is populated
  - confidence
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cactus


def dummy_set_reminder(message: str, when: str) -> dict:
    """Set a reminder for a specific date and time."""
    return {"message": message, "when": when}


decorated = cactus.tool(dummy_set_reminder)
agent = cactus.Cactus(tools=[decorated], stateless=True)

phrases = [
    "remind me at 6",
    "tomorrow at 10",
    "in 20 minutes",
    "remind me to call mom tomorrow at 10",
    "set a reminder to buy milk in 20 minutes",
]

print("=" * 70)
print(" Spike: Needle set_reminder Phrase Evaluation")
print("=" * 70)

for p in phrases:
    res = agent.complete(p)
    calls = res.get("function_calls", [])
    val = res.get("validation", {})
    ung = val.get("ungrounded", [])
    neg = val.get("negation", False)
    conf = res.get("confidence", 0.0)

    print(f"\nPhrase:     \"{p}\"")
    print(f"Confidence: {conf:.4f}  |  Negation: {neg}  |  Ungrounded: {ung}")
    if calls:
        for c in calls:
            print(f"  Call: {c.get('name')}")
            for k, v in c.get("arguments", {}).items():
                print(f"    {k}: {repr(v)}")
    else:
        print("  Call: None proposed")

agent.close()
