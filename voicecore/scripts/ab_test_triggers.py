"""A/B Test of Triggers: Current (with app names) vs Verbs-Only (no app names).

Evaluates all 115 intent cases across two configurations:
  Config A (Current):
    open_app:     ['open', 'launch', 'start', 'run', 'calculator', 'calc', 'notepad']
    search_files: ['search', 'find', 'locate', 'files', 'lookup']
    set_reminder: ['remind', 'reminder', 'schedule', 'alarm', 'timer']

  Config B (Verbs-Only):
    open_app:     ['open', 'launch', 'start', 'run']  # NO APP NAMES
    search_files: ['search', 'find', 'locate', 'files', 'lookup']
    set_reminder: ['remind', 'reminder', 'schedule', 'alarm', 'timer']
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cactus
from voicecore.config import PolicyConfig, VoiceCoreConfig
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
from voicecore.tools.registry import ToolRegistry


def to_asr_transcript(typed_text: str) -> str:
    t = typed_text.strip()
    if not t:
        return ""
    if t.endswith("?") or t.endswith("."):
        core = t[:-1].strip()
        punc = t[-1]
    else:
        core = t
        punc = "."
    return core[0].upper() + core[1:] + punc


def evaluate_config(cases: List[Dict[str, Any]], open_app_triggers: List[str], search_root: Path) -> List[Dict[str, Any]]:
    cactus.set_threads(2)
    reg = ToolRegistry()
    reg.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=open_app_triggers)
    reg.register(search_files, tier="T0", name="search_files", precheck=lambda a: search_files_precheck(a, roots=[str(search_root)]), triggers=["search", "find", "locate", "files", "lookup"])
    reg.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck, triggers=["remind", "reminder", "schedule", "alarm", "timer"])

    gate = PolicyGate(config=PolicyConfig(act_threshold=0.80, confirm_threshold=0.50), registry=reg)
    router = NeedleRouter(registry=reg, stateless=True)

    results = []
    for c in cases:
        transcript = to_asr_transcript(c["utterance"])
        route_res = router.route(transcript)

        actual_calls = [{"name": call.name, "arguments": call.arguments} for call in route_res.calls]
        exp_names = [call["name"] for call in c.get("expected_calls", [])]
        act_names = [call["name"] for call in actual_calls]

        is_correct = (exp_names == act_names)
        decision = "NO_CALLS"
        if actual_calls:
            first_call = route_res.calls[0]
            dec_obj = gate.decide(first_call, confidence=route_res.confidence, negation=route_res.negation, ungrounded=route_res.ungrounded)
            decision = dec_obj.decision

        results.append({
            "id": c.get("id"),
            "utterance": c["utterance"],
            "expected_calls": c.get("expected_calls", []),
            "actual_calls": actual_calls,
            "confidence": route_res.confidence,
            "negation": route_res.negation,
            "ungrounded": route_res.ungrounded,
            "decision": decision,
            "is_correct": is_correct,
        })
    router.close()
    return results


def main():
    search_root = Path(__file__).resolve().parent.parent / "tests" / "test_data" / "fixture_search_root"
    intents_file = Path(__file__).resolve().parent.parent / "tests" / "eval" / "intents.jsonl"
    with intents_file.open("r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    print("=" * 95)
    print(" A/B Triggers Benchmark on 115 Intent Cases")
    print(" Config A (Current):    open_app triggers include app names ['calculator', 'calc', 'notepad']")
    print(" Config B (Verbs-Only): open_app triggers contain verbs only ['open', 'launch', 'start', 'run']")
    print("=" * 95)

    print("\n[1/2] Evaluating Config A (Current: with app names)...")
    res_a = evaluate_config(cases, ["open", "launch", "start", "run", "calculator", "calc", "notepad"], search_root)

    print("\n[2/2] Evaluating Config B (Verbs-Only: without app names)...")
    res_b = evaluate_config(cases, ["open", "launch", "start", "run"], search_root)

    # Compare results
    changes = []
    conf_deltas = []
    correct_a = sum(1 for r in res_a if r["is_correct"])
    correct_b = sum(1 for r in res_b if r["is_correct"])

    for i in range(len(cases)):
        a = res_a[i]
        b = res_b[i]
        calls_a = [c["name"] for c in a["actual_calls"]]
        calls_b = [c["name"] for c in b["actual_calls"]]
        delta_conf = b["confidence"] - a["confidence"]
        conf_deltas.append(delta_conf)

        if calls_a != calls_b or a["decision"] != b["decision"] or abs(delta_conf) > 0.05:
            changes.append({
                "utterance": a["utterance"],
                "calls_a": a["actual_calls"],
                "calls_b": b["actual_calls"],
                "conf_a": a["confidence"],
                "conf_b": b["confidence"],
                "dec_a": a["decision"],
                "dec_b": b["decision"],
                "correct_a": a["is_correct"],
                "correct_b": b["is_correct"],
            })

    print("\n" + "=" * 95)
    print(" A/B COMPARISON SUMMARY (115 Cases)")
    print("=" * 95)
    print(f"  Routing Accuracy:")
    print(f"    - Config A (With App Names):  {correct_a*100.0/len(cases):.1f}% ({correct_a}/{len(cases)})")
    print(f"    - Config B (Verbs-Only):      {correct_b*100.0/len(cases):.1f}% ({correct_b}/{len(cases)})")
    print(f"  Average Confidence Delta (B - A): {sum(conf_deltas)/len(conf_deltas):+.4f}")
    print(f"  Total Cases with Route/Decision/Confidence Changes: {len(changes)} / {len(cases)}")
    print("=" * 95)

    print(f"\nDetailed Route/Decision Changes ({len(changes)} cases):")
    for ch in changes:
        print(f"  Utterance: \"{ch['utterance']}\"")
        call_str_a = f"{ch['calls_a'][0]['name']}({ch['calls_a'][0]['arguments']})" if ch['calls_a'] else "None"
        call_str_b = f"{ch['calls_b'][0]['name']}({ch['calls_b'][0]['arguments']})" if ch['calls_b'] else "None"
        print(f"    Config A: {call_str_a:<35s} | Conf: {ch['conf_a']:.4f} | Gate: {ch['dec_a']}")
        print(f"    Config B: {call_str_b:<35s} | Conf: {ch['conf_b']:.4f} | Gate: {ch['dec_b']}")
        print("    " + "-" * 75)

    out_file = Path(__file__).resolve().parent / "ab_triggers_comparison.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump({"total_cases": len(cases), "correct_a": correct_a, "correct_b": correct_b, "changes": changes}, f, indent=2)
    print(f"\nSaved A/B comparison report to {out_file}")


if __name__ == "__main__":
    main()

