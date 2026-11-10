"""Spike S2b: Diagnostic run of Needle complete() across representative edge-case utterances.

Tests:
- Negation
- Vague reference
- Two actions (multi-action)
- Off-topic
- Missing / incomplete arguments
- Standard positive baseline
"""
import json
import os
import sys

# Ensure project root / src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from voicecore.engine import NeedleAgent, tool


# Define P0 tool schemas exactly per docs/04_TOOL_SPEC.md
@tool
def open_app(app_name: str):
    """Open an application by name, for example notepad, calculator, chrome."""
    return {"ok": True, "app_name": app_name}


@tool
def set_reminder(message: str, when: str):
    """Set a reminder. `when` is a local date-time in ISO 8601, for example 2026-11-10T18:00."""
    return {"ok": True, "message": message, "when": when}


@tool
def search_files(query: str):
    """Search the user's files by file name or keyword."""
    return {"ok": True, "query": query}


TEST_PHRASES = [
    # 1. Standard positive baseline
    ("Baseline: direct open", "open notepad"),
    ("Baseline: direct search", "search files for quarterly report"),
    # 2. Negation
    ("Negation: do not open", "don't open notepad"),
    ("Negation: cancel/nevermind", "do not set a reminder for 5pm"),
    # 3. Vague reference
    ("Vague: pronoun reference", "open that app we used yesterday"),
    ("Vague: unclear target", "find the file about that thing"),
    # 4. Two actions (multi-intent)
    ("Two actions: apps", "open notepad and open calculator"),
    ("Two actions: reminder + app", "set a reminder to call mom tomorrow at 10:00 and open paint"),
    # 5. Off-topic (unsupported request / small talk)
    ("Off-topic: general QA", "what is the capital of France?"),
    ("Off-topic: conversational", "tell me a funny joke"),
    # 6. Missing / incomplete argument
    ("Missing arg: bare verb open", "open"),
    ("Missing arg: bare reminder", "set a reminder"),
]


def run_s2b():
    print("=== Initializing NeedleAgent with P0 tools ===")
    agent = NeedleAgent(tools=[open_app, set_reminder, search_files], stateless=True)

    results = []
    print("\nRunning test phrases...\n")

    for category, phrase in TEST_PHRASES:
        out = agent.complete(phrase)
        val = out.get("validation", {})
        calls = out.get("function_calls", [])
        conf = out.get("confidence", 0.0)
        res_type = out.get("type", "unknown")
        ungrounded = val.get("ungrounded", [])
        negation = val.get("negation", False)
        reasoning = out.get("reasoning", "")

        item = {
            "category": category,
            "phrase": phrase,
            "type": res_type,
            "calls": calls,
            "confidence": conf,
            "ungrounded": ungrounded,
            "negation": negation,
            "reasoning": reasoning,
            "raw": out,
        }
        results.append(item)

        print(f"[{category}] '{phrase}'")
        print(f"  -> type={res_type}, confidence={conf:.4f}")
        print(f"  -> negation={negation}, ungrounded={ungrounded}")
        print(f"  -> calls={calls}")
        print(f"  -> reasoning={reasoning[:120]}")
        print()

    agent.close()

    # Save output to json for reporting
    out_path = os.path.join(os.path.dirname(__file__), "spike_s2b_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Full results saved to {out_path}")


if __name__ == "__main__":
    run_s2b()

