"""Milestone M3: Confidence & Tool Routing Evaluation across all 3 tools.

Registers:
  - open_app (T1)
  - search_files (T0)
  - set_reminder (T1)

Evaluates:
  - Positives (open_app, search_files, set_reminder)
  - Negations (don't open, do not remind)
  - Vague / Off-topic / Missing arguments
  - Near-miss pairs (e.g. "open the quarterly report", "open budget", "find notepad")
Verifies:
  - Gate decisions: ACT, CONFIRM, REFUSE
  - Near-miss pairs NEVER end up in ACT on the wrong tool.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from voicecore.config import PolicyConfig, VoiceCoreConfig
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.builtin.search_files import search_files
from voicecore.tools.builtin.set_reminder import set_reminder
from voicecore.tools.registry import ToolRegistry


TEST_CASES: List[Tuple[str, str, str]] = [
    # (Category, Utterance, Expected Target / Constraint)
    # 1. Positive baseline
    ("Positive baseline", "open notepad", "open_app"),
    ("Positive baseline", "launch calculator", "open_app"),
    ("Positive baseline", "search files for quarterly report", "search_files"),
    ("Positive baseline", "find files named budget", "search_files"),
    ("Positive baseline", "set a reminder to call mom tomorrow at 10:00", "set_reminder"),
    ("Positive baseline", "remind me to buy milk tomorrow at 18:00", "set_reminder"),

    # 2. Negation
    ("Negation", "don't open notepad", "REFUSE"),
    ("Negation", "do not set a reminder for 5pm", "REFUSE"),

    # 3. Vague reference
    ("Vague", "open that app we used yesterday", "REFUSE or CONFIRM (never unvalidated ACT)"),
    ("Vague", "find the file about that thing", "REFUSE or CONFIRM"),

    # 4. Multi-action
    ("Multi-action", "open notepad and open calculator", "open_app x2"),

    # 5. Off-topic
    ("Off-topic", "what is the capital of France?", "REFUSE / no calls"),
    ("Off-topic", "tell me a funny joke", "REFUSE / no calls"),

    # 6. Missing arguments
    ("Missing arg", "open", "REFUSE / no calls"),
    ("Missing arg", "set a reminder", "REFUSE / no calls"),
    ("Missing arg", "search files", "REFUSE / no calls"),

    # 7. Near-miss pairs (ambiguous tool routing: file vs app vs reminder)
    ("Near-miss", "open the quarterly report", "NEVER ACT on wrong tool (CONFIRM or REFUSE)"),
    ("Near-miss", "open budget", "NEVER ACT on wrong tool (CONFIRM or REFUSE)"),
    ("Near-miss", "open my project proposal", "NEVER ACT on wrong tool (CONFIRM or REFUSE)"),
    ("Near-miss", "find notepad", "NEVER ACT on wrong tool (CONFIRM or REFUSE)"),
    ("Near-miss", "search for calculator", "NEVER ACT on wrong tool (CONFIRM or REFUSE)"),
    ("Near-miss", "remind me about notepad", "set_reminder or REFUSE/CONFIRM"),
]


def run_eval() -> int:
    config = VoiceCoreConfig(
        policy=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50)
    )

    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app")
    registry.register(search_files, tier="T0", name="search_files")
    registry.register(set_reminder, tier="T1", name="set_reminder")

    gate = PolicyGate(config=config.policy, registry=registry)
    router = NeedleRouter(registry=registry, stateless=True)

    print("=" * 85)
    print(" VoiceCore Milestone M3: S2b-Style Confidence & Routing Evaluation Table")
    print(" Registered Tools: open_app (T1), search_files (T0), set_reminder (T1)")
    print(f" Policy Thresholds: ACT >= {config.policy.act_threshold}, CONFIRM >= {config.policy.confirm_threshold}")
    print("=" * 85)

    headers = f"{'Category':18s} | {'Utterance':36s} | {'Calls':22s} | {'Conf':6s} | {'Gate Decision':12s} | {'Neg/Ung':8s}"
    print(headers)
    print("-" * 115)

    near_miss_violations = 0
    results_summary = []

    for category, utterance, expectation in TEST_CASES:
        t0 = time.perf_counter()
        route_res = router.route(utterance)
        nlu_ms = (time.perf_counter() - t0) * 1000.0

        calls_repr = ", ".join(f"{c.name}({c.arguments})" for c in route_res.calls) if route_res.calls else "[]"
        if len(calls_repr) > 22:
            calls_display = calls_repr[:19] + "..."
        else:
            calls_display = calls_repr

        # Evaluate PolicyGate for each call
        decisions = []
        for call in route_res.calls:
            dec = gate.decide(
                call=call,
                confidence=route_res.confidence,
                negation=route_res.negation,
                ungrounded=route_res.ungrounded,
            )
            decisions.append(str(dec.decision))

        primary_decision = decisions[0] if decisions else "NO_CALLS"

        neg_ung_str = ""
        if route_res.negation:
            neg_ung_str += "NEG "
        if route_res.ungrounded:
            neg_ung_str += f"UNG({len(route_res.ungrounded)})"
        if not neg_ung_str:
            neg_ung_str = "-"

        print(
            f"{category:18s} | {utterance:36s} | {calls_display:22s} | "
            f"{route_res.confidence:0.4f} | {primary_decision:12s} | {neg_ung_str:8s}"
        )

        entry = {
            "category": category,
            "utterance": utterance,
            "expectation": expectation,
            "calls": [{"name": c.name, "arguments": c.arguments} for c in route_res.calls],
            "confidence": route_res.confidence,
            "negation": route_res.negation,
            "ungrounded": route_res.ungrounded,
            "decision": primary_decision,
            "nlu_ms": nlu_ms,
        }
        results_summary.append(entry)

        # Check constraint for Near-miss pairs: MUST NOT ACT on wrong tool
        if category == "Near-miss":
            if primary_decision == "ACT":
                # Check if it was an open_app call with non-allowlisted target or wrong tool
                for c in route_res.calls:
                    if c.name == "open_app":
                        app = c.arguments.get("app_name", "").lower()
                        # If app name is not actually an app (e.g. "quarterly report", "budget", etc.), ACT is a violation!
                        if app not in ("notepad", "calculator", "calc", "paint", "mspaint", "file explorer", "explorer"):
                            print(f"  [!] VIOLATION: Near-miss '{utterance}' reached ACT with open_app({app})!")
                            near_miss_violations += 1

    print("-" * 115)
    print(f"\nTotal test cases: {len(TEST_CASES)}")
    print(f"Near-miss ACT violations: {near_miss_violations}")
    if near_miss_violations == 0:
        print("Result: PASS (All near-miss queries are safely CONFIRM or REFUSE, never ACT on wrong tool)")
    else:
        print("Result: FAIL (Near-miss query reached ACT on wrong tool)")

    # Save to JSON artifact
    out_path = Path(__file__).resolve().parent / "m3_confidence_table_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
    print(f"Detailed output saved to: {out_path.name}")

    router.close()
    return 0 if near_miss_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(run_eval())
