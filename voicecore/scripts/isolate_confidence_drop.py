"""Isolate the confidence drop across tool registration steps:

Step 1: open_app alone
Step 2: open_app + search_files
Step 3: open_app + search_files + set_reminder (current baseline)
Step 4: open_app + search_files + set_reminder with triggers=[...] and refined docstrings

Evaluates all 22 phrases at each step, reports confidence table, and analyzes what triggers do.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cactus
from voicecore.engine import tool as engine_tool
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
from voicecore.tools.registry import ToolRegistry

PHRASES = [
    # Positive baselines
    "open notepad",
    "launch calculator",
    "search files for quarterly report",
    "find files named budget",
    "set a reminder to call mom tomorrow at 10:00",
    "remind me to buy milk tomorrow at 18:00",
    # Negations
    "don't open notepad",
    "do not set a reminder for 5pm",
    # Vague
    "open that app we used yesterday",
    "find the file about that thing",
    # Multi-action
    "open notepad and open calculator",
    # Off-topic
    "what is the capital of France?",
    "tell me a funny joke",
    # Missing args
    "open",
    "set a reminder",
    "search files",
    # Near-miss
    "open the quarterly report",
    "open budget",
    "open my project proposal",
    "find notepad",
    "search for calculator",
    "remind me about notepad",
]


def eval_router(router: NeedleRouter) -> List[Dict[str, Any]]:
    results = []
    for p in PHRASES:
        res = router.route(p)
        call_str = ", ".join(f"{c.name}({c.arguments})" for c in res.calls) if res.calls else "[]"
        results.append({
            "utterance": p,
            "calls": call_str,
            "confidence": res.confidence,
            "negation": res.negation,
            "ungrounded": res.ungrounded,
        })
    return results


def main() -> None:
    print("=" * 80)
    print(" VoiceCore: Isolating Confidence Drop Across Tool Registrations")
    print("=" * 80)

    # --- STEP 1: open_app alone ---
    reg1 = ToolRegistry()
    reg1.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck)
    router1 = NeedleRouter(registry=reg1, stateless=True)
    res1 = eval_router(router1)
    router1.close()

    # --- STEP 2: open_app + search_files ---
    reg2 = ToolRegistry()
    reg2.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck)
    reg2.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck)
    router2 = NeedleRouter(registry=reg2, stateless=True)
    res2 = eval_router(router2)
    router2.close()

    # --- STEP 3: open_app + search_files + set_reminder ---
    reg3 = ToolRegistry()
    reg3.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck)
    reg3.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck)
    reg3.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck)
    router3 = NeedleRouter(registry=reg3, stateless=True)
    res3 = eval_router(router3)
    router3.close()

    # --- STEP 4: with triggers=[...] ---
    @cactus.tool(triggers=["open", "launch", "start"])
    def open_app_triggered(app_name: str):
        """Open an installed desktop application by name (e.g. notepad, calculator, paint)."""
        return open_app(app_name)

    @cactus.tool(triggers=["search files", "find files", "search local"])
    def search_files_triggered(query: str):
        """Search local documents for a file whose name contains query."""
        return search_files(query)

    @cactus.tool(triggers=["remind", "reminder", "schedule"])
    def set_reminder_triggered(message: str, when: str):
        """Set a scheduled reminder with a message and a future time."""
        return set_reminder(message, when)

    agent4 = cactus.Cactus(tools=[open_app_triggered, search_files_triggered, set_reminder_triggered], stateless=True)
    res4 = []
    for p in PHRASES:
        out = agent4.complete(p)
        calls = out.get("function_calls", [])
        c_str = ", ".join(f"{c['name']}({c.get('arguments')})" for c in calls) if calls else "[]"
        res4.append({
            "utterance": p,
            "calls": c_str,
            "confidence": float(out.get("confidence", 0.0)),
            "negation": bool(out.get("validation", {}).get("negation", False)),
            "ungrounded": list(out.get("validation", {}).get("ungrounded", [])),
        })
    agent4.close()

    # --- Print comparative table ---
    print(f"\n{'Utterance':38s} | {'Step 1 (1 tool)':15s} | {'Step 2 (+search)':15s} | {'Step 3 (+remind)':15s} | {'Step 4 (+triggers)':15s}")
    print("-" * 105)

    comparison_data = []
    for i, p in enumerate(PHRASES):
        c1 = res1[i]["confidence"]
        c2 = res2[i]["confidence"]
        c3 = res3[i]["confidence"]
        c4 = res4[i]["confidence"]
        print(f"{p:38s} | {c1:15.4f} | {c2:15.4f} | {c3:15.4f} | {c4:15.4f}")
        comparison_data.append({
            "utterance": p,
            "step1_open_app_alone": {"confidence": c1, "calls": res1[i]["calls"]},
            "step2_plus_search_files": {"confidence": c2, "calls": res2[i]["calls"]},
            "step3_plus_set_reminder": {"confidence": c3, "calls": res3[i]["calls"]},
            "step4_with_triggers": {"confidence": c4, "calls": res4[i]["calls"]},
        })

    print("-" * 105)

    out_file = Path(__file__).resolve().parent / "confidence_drop_analysis.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(comparison_data, f, indent=2)
    print(f"\nSaved comparison data to {out_file.name}")


if __name__ == "__main__":
    main()
