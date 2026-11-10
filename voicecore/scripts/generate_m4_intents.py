"""Generate 105 balanced intent evaluation cases for Milestone M4.

Categories:
  - 15 open_app single action
  - 15 search_files single action
  - 15 set_reminder single action
  - 10 multi-action
  - 10 negation
  - 10 vague / missing args
  - 10 off-topic / unsupported / forbidden
  - 30 near-miss ambiguous collisions

Saves to tests/eval/intents.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

INTENTS = [
    # 1. open_app (15)
    {"utterance": "open notepad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "open_app"},
    {"utterance": "launch calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"utterance": "open calc", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calc"}}], "category": "open_app"},
    {"utterance": "start paint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "open_app"},
    {"utterance": "open file explorer", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "file explorer"}}], "category": "open_app"},
    {"utterance": "please open the notepad application", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "open_app"},
    {"utterance": "bring up calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"utterance": "open mspaint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "mspaint"}}], "category": "open_app"},
    {"utterance": "launch paint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "open_app"},
    {"utterance": "run calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"utterance": "start explorer", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "explorer"}}], "category": "open_app"},
    {"utterance": "open node pad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "node pad"}}], "category": "open_app"},
    {"utterance": "please open calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"utterance": "can you launch notepad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "open_app"},
    {"utterance": "open the paint application", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "open_app"},

    # 2. search_files (15)
    {"utterance": "search files for quarterly report", "expected_calls": [{"name": "search_files", "arguments": {"query": "quarterly report"}}], "category": "search_files"},
    {"utterance": "find files named budget", "expected_calls": [{"name": "search_files", "arguments": {"query": "budget"}}], "category": "search_files"},
    {"utterance": "search local files for project proposal", "expected_calls": [{"name": "search_files", "arguments": {"query": "project proposal"}}], "category": "search_files"},
    {"utterance": "find my resume file", "expected_calls": [{"name": "search_files", "arguments": {"query": "resume"}}], "category": "search_files"},
    {"utterance": "search files for invoice", "expected_calls": [{"name": "search_files", "arguments": {"query": "invoice"}}], "category": "search_files"},
    {"utterance": "find files called report", "expected_calls": [{"name": "search_files", "arguments": {"query": "report"}}], "category": "search_files"},
    {"utterance": "search for meeting notes file", "expected_calls": [{"name": "search_files", "arguments": {"query": "meeting notes"}}], "category": "search_files"},
    {"utterance": "look for files named presentation", "expected_calls": [{"name": "search_files", "arguments": {"query": "presentation"}}], "category": "search_files"},
    {"utterance": "search files containing proposal", "expected_calls": [{"name": "search_files", "arguments": {"query": "proposal"}}], "category": "search_files"},
    {"utterance": "find spreadsheet named taxes", "expected_calls": [{"name": "search_files", "arguments": {"query": "taxes"}}], "category": "search_files"},
    {"utterance": "locate file named checklist", "expected_calls": [{"name": "search_files", "arguments": {"query": "checklist"}}], "category": "search_files"},
    {"utterance": "search documents for summary", "expected_calls": [{"name": "search_files", "arguments": {"query": "summary"}}], "category": "search_files"},
    {"utterance": "find pdf named contract", "expected_calls": [{"name": "search_files", "arguments": {"query": "contract"}}], "category": "search_files"},
    {"utterance": "search my files for schedule", "expected_calls": [{"name": "search_files", "arguments": {"query": "schedule"}}], "category": "search_files"},
    {"utterance": "find file named design", "expected_calls": [{"name": "search_files", "arguments": {"query": "design"}}], "category": "search_files"},

    # 3. set_reminder (15)
    {"utterance": "set a reminder to call mom tomorrow at 10:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "call mom", "when": "tomorrow at 10:00"}}], "category": "set_reminder"},
    {"utterance": "remind me to buy milk tomorrow at 18:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "buy milk", "when": "tomorrow at 18:00"}}], "category": "set_reminder"},
    {"utterance": "set a reminder for team meeting tomorrow at 09:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "team meeting", "when": "tomorrow at 09:00"}}], "category": "set_reminder"},
    {"utterance": "remind me to take medication in 20 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "take medication", "when": "in 20 minutes"}}], "category": "set_reminder"},
    {"utterance": "set a reminder for dentist appointment tomorrow at 14:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "dentist appointment", "when": "tomorrow at 14:00"}}], "category": "set_reminder"},
    {"utterance": "remind me to submit timesheet tomorrow at 17:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "submit timesheet", "when": "tomorrow at 17:00"}}], "category": "set_reminder"},
    {"utterance": "set a reminder to check oven in 30 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "check oven", "when": "in 30 minutes"}}], "category": "set_reminder"},
    {"utterance": "remind me to call John at 15:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "call John", "when": "at 15:00"}}], "category": "set_reminder"},
    {"utterance": "set a reminder for standup tomorrow at 10:30", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "standup", "when": "tomorrow at 10:30"}}], "category": "set_reminder"},
    {"utterance": "remind me to pay bills tomorrow at 12:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "pay bills", "when": "tomorrow at 12:00"}}], "category": "set_reminder"},
    {"utterance": "set a reminder to stretch in 1 hour", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "stretch", "when": "in 1 hour"}}], "category": "set_reminder"},
    {"utterance": "remind me to pick up groceries at 6pm", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "pick up groceries", "when": "at 6pm"}}], "category": "set_reminder"},
    {"utterance": "set a reminder for project review tomorrow at 11:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "project review", "when": "tomorrow at 11:00"}}], "category": "set_reminder"},
    {"utterance": "remind me to drink water in 15 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "drink water", "when": "in 15 minutes"}}], "category": "set_reminder"},
    {"utterance": "set a reminder to send email tomorrow at 08:30", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "send email", "when": "tomorrow at 08:30"}}], "category": "set_reminder"},

    # 4. Multi-action (10)
    {"utterance": "open notepad and open calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}, {"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "multi_action"},
    {"utterance": "open paint and open notepad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}, {"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "multi_action"},
    {"utterance": "open calc and launch paint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calc"}}, {"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "multi_action"},
    {"utterance": "set a reminder to call mom tomorrow at 10:00 and open notepad", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "call mom", "when": "tomorrow at 10:00"}}, {"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "multi_action"},
    {"utterance": "open calculator and search files for budget", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}, {"name": "search_files", "arguments": {"query": "budget"}}], "category": "multi_action"},
    {"utterance": "open file explorer and open notepad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "file explorer"}}, {"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "multi_action"},
    {"utterance": "set a reminder to buy milk tomorrow at 18:00 and open calculator", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "buy milk", "when": "tomorrow at 18:00"}}, {"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "multi_action"},
    {"utterance": "launch paint and open calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}, {"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "multi_action"},
    {"utterance": "search files for quarterly report and open notepad", "expected_calls": [{"name": "search_files", "arguments": {"query": "quarterly report"}}, {"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "multi_action"},
    {"utterance": "open notepad and open paint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}, {"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "multi_action"},

    # 5. Negation (10)
    {"utterance": "don't open notepad", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "do not set a reminder for 5pm", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "never open calculator", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "don't search files for secret", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "do not open paint", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "please don't launch calculator", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "nevermind do not set a reminder", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "cancel that don't open notepad", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "do not find files named budget", "expected_calls": [], "category": "negative_negation"},
    {"utterance": "don't set any reminders", "expected_calls": [], "category": "negative_negation"},

    # 6. Vague / Missing argument (10)
    {"utterance": "open that app we used yesterday", "expected_calls": [], "category": "negative_vague"},
    {"utterance": "find the file about that thing", "expected_calls": [], "category": "negative_vague"},
    {"utterance": "remind me about that stuff", "expected_calls": [], "category": "negative_vague"},
    {"utterance": "open the recent thing", "expected_calls": [], "category": "negative_vague"},
    {"utterance": "search files for whatever", "expected_calls": [], "category": "negative_vague"},
    {"utterance": "open", "expected_calls": [], "category": "negative_missing_arg"},
    {"utterance": "launch", "expected_calls": [], "category": "negative_missing_arg"},
    {"utterance": "search files", "expected_calls": [], "category": "negative_missing_arg"},
    {"utterance": "find file", "expected_calls": [], "category": "negative_missing_arg"},
    {"utterance": "set a reminder", "expected_calls": [], "category": "negative_missing_arg"},

    # 7. Off-topic / Unsupported / Forbidden T2 (10)
    {"utterance": "what is the capital of France?", "expected_calls": [], "category": "negative_off_topic"},
    {"utterance": "tell me a funny joke", "expected_calls": [], "category": "negative_off_topic"},
    {"utterance": "who won the world cup in 2022?", "expected_calls": [], "category": "negative_off_topic"},
    {"utterance": "play some jazz music on spotify", "expected_calls": [], "category": "negative_unsupported"},
    {"utterance": "how is the weather outside today?", "expected_calls": [], "category": "negative_unsupported"},
    {"utterance": "good morning how are you doing", "expected_calls": [], "category": "negative_smalltalk"},
    {"utterance": "delete all files in documents", "expected_calls": [], "category": "negative_forbidden_t2"},
    {"utterance": "send an email to my manager", "expected_calls": [], "category": "negative_forbidden_t2"},
    {"utterance": "shutdown the computer immediately", "expected_calls": [], "category": "negative_forbidden_t2"},
    {"utterance": "format drive c", "expected_calls": [], "category": "negative_forbidden_t2"},

    # 8. Near-miss ambiguous pairs (30)
    {"utterance": "open the quarterly report", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open budget", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open my project proposal", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open invoice", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open presentation", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open notes", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open my resume", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open document", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open report", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open sheet", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open summary", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open draft", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open paper", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open text file", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open log", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "find notepad", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "search for calculator", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "locate paint", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "search files for notepad", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "find calc", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "search for file explorer", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "look for notepad on my computer", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "search for mspaint", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "find the notepad tool", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "search for the calculator program", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "remind me about notepad", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "remind me of the calculator", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "remind me to find budget", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "set a reminder about quarterly report", "expected_calls": [], "category": "negative_near_miss"},
    {"utterance": "open reminder", "expected_calls": [], "category": "negative_near_miss"},
]


def main():
    target = Path(__file__).resolve().parent.parent / "tests" / "eval" / "intents.jsonl"
    with target.open("w", encoding="utf-8") as f:
        for item in INTENTS:
            f.write(json.dumps(item) + "\n")
    print(f"Generated {len(INTENTS)} intents into {target}")


if __name__ == "__main__":
    main()
