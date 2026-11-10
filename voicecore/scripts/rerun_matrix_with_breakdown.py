"""Re-run matrix with search.roots fixture and complete refusal breakdown.

Evaluates 115 intent cases with:
- search.roots pointing to tests/test_data/fixture_search_root
- triggers explicitly ACTIVE on all tools
- breakdown of every REFUSE by reason:
    1. precheck
    2. negation
    3. ungrounded
    4. below confirm threshold
- subset of wrong-tool / negative cases whose arguments pass precheck
- exact numbers for per-tier T0 policy
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

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
    if t.endswith("?"):
        punc = "?"
        core = t[:-1].strip()
    elif t.endswith("."):
        punc = "."
        core = t[:-1].strip()
    else:
        punc = "."
        core = t
    return core[0].upper() + core[1:] + punc


def main():
    cactus.set_threads(2)

    fixture_dir = Path(__file__).resolve().parent.parent / "tests" / "test_data" / "fixture_search_root"
    assert fixture_dir.is_dir(), f"Fixture dir missing: {fixture_dir}"

    triggers_active = True
    open_app_triggers = ["open", "launch", "start", "run", "calculator", "calc", "notepad"]
    search_files_triggers = ["search", "find", "locate", "files", "lookup"]
    set_reminder_triggers = ["remind", "reminder", "schedule", "alarm", "timer"]

    registry = ToolRegistry()
    registry.register(
        open_app,
        tier="T1",
        name="open_app",
        precheck=open_app_precheck,
        triggers=open_app_triggers,
    )
    registry.register(
        search_files,
        tier="T0",
        name="search_files",
        precheck=lambda args: search_files_precheck(args, roots=[str(fixture_dir)]),
        triggers=search_files_triggers,
    )
    registry.register(
        set_reminder,
        tier="T1",
        name="set_reminder",
        precheck=set_reminder_precheck,
        triggers=set_reminder_triggers,
    )

    router = NeedleRouter(registry=registry, stateless=True)

    intents_file = Path(__file__).resolve().parent.parent / "tests" / "eval" / "intents.jsonl"
    with intents_file.open("r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    print("=" * 90)
    print(" VoiceCore: Evaluation Matrix with search.roots Fixture & Refusal Breakdown")
    print(f" Dataset: {len(cases)} cases from tests/eval/intents.jsonl")
    print(f" search.roots fixture: {fixture_dir}")
    print(f" Triggers active: {triggers_active}")
    print(f"   open_app triggers:      {open_app_triggers}")
    print(f"   search_files triggers:  {search_files_triggers}")
    print(f"   set_reminder triggers:  {set_reminder_triggers}")
    print("=" * 90)

    # Route all cases
    routed_cases = []
    t_start = time.perf_counter()
    for idx, c in enumerate(cases):
        utterance = c["utterance"]
        transcript = to_asr_transcript(utterance)
        route_res = router.route(transcript)

        actual_calls = [{"name": call.name, "arguments": call.arguments} for call in route_res.calls]
        expected_calls = c.get("expected_calls", [])

        # Tool match determination
        act_names = [call["name"] for call in actual_calls]
        exp_names = [call["name"] for call in expected_calls]

        is_correct = (act_names == exp_names)
        is_wrong_tool = (len(act_names) > 0 and act_names != exp_names)
        is_negative = (len(exp_names) == 0)

        routed_cases.append({
            "idx": idx,
            "utterance": utterance,
            "transcript": transcript,
            "expected_calls": expected_calls,
            "actual_calls": actual_calls,
            "confidence": route_res.confidence,
            "negation": route_res.negation,
            "ungrounded": route_res.ungrounded,
            "is_correct": is_correct,
            "is_wrong_tool": is_wrong_tool,
            "is_negative": is_negative,
            "category": c.get("category", ""),
        })

    total_route_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Routing completed in {total_route_ms:.1f} ms ({total_route_ms/len(cases):.1f} ms/case)\n")

    # Evaluate across 3 policy configurations
    configs = [
        ("Current Policy (ACT=0.80, CONFIRM=0.50)", 0.80, 0.50, False),
        ("Proposed Policy (ACT=0.70, CONFIRM=0.35)", 0.70, 0.35, False),
        ("Per-Tier Policy (T0: 0.40/0.25, T1: 0.70/0.35)", 0.70, 0.35, True),
    ]

    tier_map = {"open_app": "T1", "set_reminder": "T1", "search_files": "T0"}

    for cfg_title, base_act, base_conf, is_per_tier in configs:
        print(f"\n{'='*90}")
        print(f" POLICY EVALUATION: {cfg_title}")
        print(f"{'='*90}")

        # Breakdown counters
        # Category totals
        totals = {
            "all_correct": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "open_app": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "search_files": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "set_reminder": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "tier_t0": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "tier_t1": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "wrong_or_neg": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
        }

        # Detailed REFUSE reasons per tool
        refuse_reasons = {
            "open_app": {"precheck": 0, "negation": 0, "ungrounded": 0, "below_confirm": 0, "no_call": 0},
            "search_files": {"precheck": 0, "negation": 0, "ungrounded": 0, "below_confirm": 0, "no_call": 0},
            "set_reminder": {"precheck": 0, "negation": 0, "ungrounded": 0, "below_confirm": 0, "no_call": 0},
            "wrong_or_neg": {"precheck": 0, "negation": 0, "ungrounded": 0, "below_confirm": 0, "no_call": 0},
        }

        # Track wrong/negative cases whose args pass precheck
        wrong_args_pass_precheck = []

        for item in routed_cases:
            calls = item["actual_calls"]
            conf = item["confidence"]
            neg = item["negation"]
            ung = item["ungrounded"]
            is_corr = item["is_correct"]
            expected = item["expected_calls"]

            if not calls:
                # No calls generated
                if expected:
                    for exp in expected:
                        t_name = exp["name"]
                        tier = tier_map.get(t_name, "T1")
                        totals["all_correct"]["REFUSE"] += 1
                        totals["all_correct"]["total"] += 1
                        totals[t_name]["REFUSE"] += 1
                        totals[t_name]["total"] += 1
                        if tier == "T0":
                            totals["tier_t0"]["REFUSE"] += 1
                            totals["tier_t0"]["total"] += 1
                        else:
                            totals["tier_t1"]["REFUSE"] += 1
                            totals["tier_t1"]["total"] += 1
                        refuse_reasons[t_name]["no_call"] += 1
                else:
                    totals["wrong_or_neg"]["REFUSE"] += 1
                    totals["wrong_or_neg"]["total"] += 1
                    refuse_reasons["wrong_or_neg"]["no_call"] += 1
                continue

            # Calls were generated
            for call in calls:
                tool_name = call["name"]
                tool_args = call.get("arguments", {})
                tier = tier_map.get(tool_name, "T1")

                # Determine effective thresholds
                if is_per_tier and tier == "T0":
                    act_thresh = 0.40
                    conf_thresh = 0.25
                else:
                    act_thresh = base_act
                    conf_thresh = base_conf

                # Evaluate precheck
                tool_def = registry.get(tool_name)
                precheck_ok = True
                precheck_msg = ""
                if tool_def and tool_def.precheck:
                    try:
                        precheck_ok, precheck_msg = tool_def.precheck(tool_args)
                    except Exception as ex:
                        precheck_ok, precheck_msg = False, str(ex)

                # Determine Gate Decision & Reason
                if neg:
                    decision = "REFUSE"
                    primary_reason = "negation"
                elif ung:
                    decision = "REFUSE"
                    primary_reason = "ungrounded"
                elif not precheck_ok:
                    decision = "REFUSE"
                    primary_reason = "precheck"
                elif conf < conf_thresh:
                    decision = "REFUSE"
                    primary_reason = "below_confirm"
                elif conf >= act_thresh:
                    decision = "ACT"
                    primary_reason = "act"
                else:
                    decision = "CONFIRM"
                    primary_reason = "confirm"

                # Check wrong-tool / negative cases passing precheck
                if (not is_corr or not expected) and precheck_ok:
                    wrong_args_pass_precheck.append({
                        "utterance": item["utterance"],
                        "actual_tool": tool_name,
                        "args": tool_args,
                        "confidence": conf,
                        "decision": decision,
                        "reason": primary_reason,
                    })

                # Tally
                if is_corr and expected:
                    totals["all_correct"][decision] += 1
                    totals["all_correct"]["total"] += 1
                    totals[tool_name][decision] += 1
                    totals[tool_name]["total"] += 1
                    if tier == "T0":
                        totals["tier_t0"][decision] += 1
                        totals["tier_t0"]["total"] += 1
                    else:
                        totals["tier_t1"][decision] += 1
                        totals["tier_t1"]["total"] += 1
                    if decision == "REFUSE":
                        refuse_reasons[tool_name][primary_reason] += 1
                else:
                    totals["wrong_or_neg"][decision] += 1
                    totals["wrong_or_neg"]["total"] += 1
                    if decision == "REFUSE":
                        refuse_reasons["wrong_or_neg"][primary_reason] += 1

        def pct(part: int, tot: int) -> str:
            if tot == 0:
                return "0.0% (0/0)"
            return f"{part*100.0/tot:5.1f}% ({part}/{tot})"

        print(f"\n  Summary Table ({cfg_title}):")
        print(f"  {'Category / Target':30s} | {'% ACT':18s} | {'% CONFIRM':18s} | {'% REFUSE':18s}")
        print(f"  {'-'*85}")
        for k, label in [
            ("all_correct", "All Correct Commands"),
            ("open_app", "Tool: open_app (T1)"),
            ("search_files", "Tool: search_files (T0)"),
            ("set_reminder", "Tool: set_reminder (T1)"),
            ("tier_t0", "Tier T0 (Read-Only)"),
            ("tier_t1", "Tier T1 (Reversible Actions)"),
            ("wrong_or_neg", "Wrong-Tool / Negatives"),
        ]:
            b = totals[k]
            tot = b["total"]
            print(f"  {label:30s} | {pct(b['ACT'], tot):18s} | {pct(b['CONFIRM'], tot):18s} | {pct(b['REFUSE'], tot):18s}")

        print(f"\n  Breakdown of REFUSE Decisions by Cause:")
        print(f"  {'Target Tool / Category':25s} | {'Total REFUSE':12s} | {'Precheck':10s} | {'Negation':10s} | {'Ungrounded':12s} | {'Below Conf':12s} | {'No Call':10s}")
        print(f"  {'-'*95}")
        for t_k, t_lbl in [
            ("open_app", "open_app (T1)"),
            ("search_files", "search_files (T0)"),
            ("set_reminder", "set_reminder (T1)"),
            ("wrong_or_neg", "Wrong-Tool / Negatives"),
        ]:
            r_b = refuse_reasons[t_k]
            t_ref = sum(r_b.values())
            print(f"  {t_lbl:25s} | {t_ref:<12d} | {r_b['precheck']:<10d} | {r_b['negation']:<10d} | {r_b['ungrounded']:<12d} | {r_b['below_confirm']:<12d} | {r_b['no_call']:<10d}")

        print(f"\n  Subset of Wrong-Tool or Negative Cases whose Arguments PASS Precheck:")
        print(f"  Total occurrences: {len(wrong_args_pass_precheck)}")
        for w in wrong_args_pass_precheck:
            print(f"    - Utterance: \"{w['utterance']}\"")
            print(f"      Routed Tool: {w['actual_tool']}, Args: {w['args']}")
            print(f"      Confidence: {w['confidence']:.4f} -> Decision: {w['decision']} (Reason: {w['reason']})")

    # Save detailed data to json
    out_path = Path(__file__).resolve().parent / "fixture_eval_matrix.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "fixture_dir": str(fixture_dir),
            "triggers_active": triggers_active,
            "routed_cases": routed_cases,
        }, f, indent=2)
    print(f"\nSaved detailed evaluation trace to: {out_path}")


if __name__ == "__main__":
    main()

