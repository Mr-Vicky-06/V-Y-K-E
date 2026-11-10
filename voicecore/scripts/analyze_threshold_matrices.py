"""Threshold Confusion Matrix & Trade-off Analysis.

Evaluates the 115 test cases across 3 policy configurations:
  Config 1 (Current):  ACT >= 0.80, CONFIRM >= 0.50
  Config 2 (Proposed): ACT >= 0.70, CONFIRM >= 0.35
  Config 3 (Per-Tier): T0 (ACT >= 0.40, CONF >= 0.25), T1 (ACT >= 0.70, CONF >= 0.35)

Reports:
  - % ACT / CONFIRM / REFUSE for correct commands:
    * Overall
    * Per tool (open_app, search_files, set_reminder)
    * Per tier (Tier T0 vs Tier T1)
  - % ACT for wrong-tool or negative cases (Must be 0%)
  - Trade-off analysis of per-tier thresholds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def evaluate_gate_decision(
    call_name: str,
    args: Dict[str, Any],
    confidence: float,
    negation: bool,
    ungrounded: List[str],
    tier: str,
    act_thresh: float,
    conf_thresh: float,
    has_precheck_failure: bool,
) -> str:
    if negation or ungrounded:
        return "REFUSE"
    if tier == "T2":
        return "REFUSE"
    if has_precheck_failure:
        return "REFUSE"
    if confidence >= act_thresh:
        return "ACT"
    if confidence >= conf_thresh:
        return "CONFIRM"
    return "REFUSE"


def analyze():
    report_file = Path(__file__).resolve().parent / "m4_eval_report.json"
    with report_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    configs = [
        ("Current (0.80 / 0.50)", 0.80, 0.50, False),
        ("Proposed Uniform (0.70 / 0.35)", 0.70, 0.35, False),
        ("Per-Tier (T0: 0.40/0.25, T1: 0.70/0.35)", 0.70, 0.35, True),
    ]

    tier_map = {
        "open_app": "T1",
        "set_reminder": "T1",
        "search_files": "T0",
    }

    print("=" * 90)
    print(" VoiceCore: Threshold Matrix & Trade-off Analysis (115 ASR Test Cases)")
    print("=" * 90)

    for cfg_name, base_act, base_conf, is_per_tier in configs:
        print(f"\n{'─'*90}")
        print(f" Policy Configuration: {cfg_name}")
        print(f"{'─'*90}")

        # Metrics buckets
        counts = {
            "all_correct": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "open_app": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "search_files": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "set_reminder": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "tier_t0": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "tier_t1": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
            "wrong_or_neg": {"ACT": 0, "CONFIRM": 0, "REFUSE": 0, "total": 0},
        }

        for c in cases:
            calls = c["actual_calls"]
            conf = c["confidence"]
            neg = c["negation"]
            ung = c["ungrounded"]
            is_correct = c["is_correct"]
            is_wrong = c["is_wrong_tool"]
            expected = c["expected_calls"]

            # Check precheck failure from recorded decisions
            has_precheck_fail = any("Pre-check failed" in d.get("reason", "") for d in c["decisions"])

            if not calls:
                # No calls proposed
                if not expected:
                    counts["wrong_or_neg"]["REFUSE"] += 1
                    counts["wrong_or_neg"]["total"] += 1
                else:
                    for exp in expected:
                        t_name = exp["name"]
                        tier = tier_map.get(t_name, "T1")
                        counts["all_correct"]["REFUSE"] += 1
                        counts["all_correct"]["total"] += 1
                        counts[t_name]["REFUSE"] += 1
                        counts[t_name]["total"] += 1
                        if tier == "T0":
                            counts["tier_t0"]["REFUSE"] += 1
                            counts["tier_t0"]["total"] += 1
                        else:
                            counts["tier_t1"]["REFUSE"] += 1
                            counts["tier_t1"]["total"] += 1
                continue

            for call in calls:
                call_name = call["name"]
                tier = tier_map.get(call_name, "T1")

                if is_per_tier and tier == "T0":
                    act_th = 0.40
                    conf_th = 0.25
                else:
                    act_th = base_act
                    conf_th = base_conf

                dec = evaluate_gate_decision(
                    call_name=call_name,
                    args=call.get("arguments", {}),
                    confidence=conf,
                    negation=neg,
                    ungrounded=ung,
                    tier=tier,
                    act_thresh=act_th,
                    conf_thresh=conf_th,
                    has_precheck_failure=has_precheck_fail,
                )

                if is_correct and expected:
                    counts["all_correct"][dec] += 1
                    counts["all_correct"]["total"] += 1
                    counts[call_name][dec] += 1
                    counts[call_name]["total"] += 1
                    if tier == "T0":
                        counts["tier_t0"][dec] += 1
                        counts["tier_t0"]["total"] += 1
                    else:
                        counts["tier_t1"][dec] += 1
                        counts["tier_t1"]["total"] += 1
                else:
                    counts["wrong_or_neg"][dec] += 1
                    counts["wrong_or_neg"]["total"] += 1

        def pct(part: int, tot: int) -> str:
            if tot == 0:
                return "0.0%"
            return f"{part*100.0/tot:5.1f}% ({part}/{tot})"

        print(f"  {'Category / Target':30s} | {'% ACT':18s} | {'% CONFIRM':18s} | {'% REFUSE':18s}")
        print(f"  {'-'*85}")
        for key, label in [
            ("all_correct", "All Correct Commands"),
            ("open_app", "Tool: open_app (T1)"),
            ("search_files", "Tool: search_files (T0)"),
            ("set_reminder", "Tool: set_reminder (T1)"),
            ("tier_t0", "Tier T0 (Read-Only)"),
            ("tier_t1", "Tier T1 (Reversible Actions)"),
            ("wrong_or_neg", "Wrong-Tool / Negatives"),
        ]:
            b = counts[key]
            tot = b["total"]
            print(f"  {label:30s} | {pct(b['ACT'], tot):18s} | {pct(b['CONFIRM'], tot):18s} | {pct(b['REFUSE'], tot):18s}")


if __name__ == "__main__":
    analyze()
