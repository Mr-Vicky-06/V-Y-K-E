"""Unit and safety tests for set_reminder (T1).

Verifies:
  - Local time stored with UTC offset
  - Parsing: "in 20 minutes", "tomorrow at 10", "at 6pm", ISO strings
  - Past time rejection
  - Empty message rejection
  - SQLite persistence and schema
  - Timer execution (Event / Callback fired when due)
  - Reload on restart: future re-scheduled, past marked 'missed' and NOT fired
  - Explicit warning notice returned in result
"""
from __future__ import annotations

import datetime
from pathlib import Path
import sqlite3
import time

import pytest

from voicecore.tools.builtin.set_reminder import (
    Reminder,
    ReminderManager,
    parse_target_time,
)


@pytest.fixture()
def fixed_now() -> datetime.datetime:
    """Fixed reference time in a specific timezone (+05:30) for deterministic tests."""
    tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime(2026, 11, 10, 14, 0, 0, tzinfo=tz)


@pytest.fixture()
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_reminders.db"


# ---------------------------------------------------------------------------
# Time parsing unit tests
# ---------------------------------------------------------------------------

def test_parse_relative_in_20_minutes(fixed_now: datetime.datetime) -> None:
    dt = parse_target_time("in 20 minutes", reference_time=fixed_now)
    assert dt == fixed_now + datetime.timedelta(minutes=20)
    assert dt.utcoffset() == datetime.timedelta(hours=5, minutes=30)
    assert dt.isoformat().endswith("+05:30")


def test_parse_relative_in_2_hours(fixed_now: datetime.datetime) -> None:
    dt = parse_target_time("in 2 hours", reference_time=fixed_now)
    assert dt == fixed_now + datetime.timedelta(hours=2)


def test_parse_tomorrow_at_10(fixed_now: datetime.datetime) -> None:
    dt = parse_target_time("tomorrow at 10", reference_time=fixed_now)
    expected = datetime.datetime(2026, 11, 11, 10, 0, 0, tzinfo=fixed_now.tzinfo)
    assert dt == expected
    assert dt.utcoffset() is not None


def test_parse_tomorrow_at_10_pm(fixed_now: datetime.datetime) -> None:
    dt = parse_target_time("tomorrow at 10 pm", reference_time=fixed_now)
    expected = datetime.datetime(2026, 11, 11, 22, 0, 0, tzinfo=fixed_now.tzinfo)
    assert dt == expected


def test_parse_needle_partial_date(fixed_now: datetime.datetime) -> None:
    # Needle often outputs "2026-11-11 10"
    dt = parse_target_time("2026-11-11 10", reference_time=fixed_now)
    expected = datetime.datetime(2026, 11, 11, 10, 0, 0, tzinfo=fixed_now.tzinfo)
    assert dt == expected


def test_parse_iso_string(fixed_now: datetime.datetime) -> None:
    iso = "2026-11-12T09:30:00+05:30"
    dt = parse_target_time(iso, reference_time=fixed_now)
    assert dt.isoformat() == iso


def test_parse_invalid_string_raises() -> None:
    with pytest.raises(ValueError):
        parse_target_time("some gibberish time")


# ---------------------------------------------------------------------------
# ReminderManager operational tests
# ---------------------------------------------------------------------------

def test_set_reminder_success(temp_db: Path, fixed_now: datetime.datetime) -> None:
    mgr = ReminderManager(db_path=temp_db)
    res = mgr.set_reminder(
        message="Call mom",
        when="tomorrow at 10",
        reference_time=fixed_now,
    )
    mgr.cancel_all()

    assert res["ok"] is True
    assert res["message"] == "Call mom"
    assert "2026-11-11T10:00:00+05:30" in res["when"]
    assert "Reminders only fire while VYKE is running" in res["notice"]

    # Verify SQLite row
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE id = ?", (res["id"],))
        row = cur.fetchone()
        assert row is not None
        assert row["message"] == "Call mom"
        assert row["status"] == "pending"
        assert "+05:30" in row["target_time_iso"]


def test_past_time_rejected(temp_db: Path, fixed_now: datetime.datetime) -> None:
    mgr = ReminderManager(db_path=temp_db)
    # 1 hour ago
    past_iso = (fixed_now - datetime.timedelta(hours=1)).isoformat()
    res = mgr.set_reminder(
        message="Past task",
        when=past_iso,
        reference_time=fixed_now,
    )
    assert res["ok"] is False
    assert res["error"] == "past_time"


def test_empty_message_rejected(temp_db: Path) -> None:
    mgr = ReminderManager(db_path=temp_db)
    res = mgr.set_reminder(message="", when="tomorrow at 10")
    assert res["ok"] is False
    assert res["error"] == "empty_message"


def test_timer_fires_when_due(temp_db: Path) -> None:
    fired_reminders = []

    def on_due(rem: Reminder) -> None:
        fired_reminders.append(rem)

    mgr = ReminderManager(db_path=temp_db, on_due=on_due)
    # Schedule 0.1s in the future
    future_iso = (datetime.datetime.now(datetime.timezone.utc).astimezone() + datetime.timedelta(seconds=0.1)).isoformat()
    res = mgr.set_reminder("Fast reminder", when=future_iso)
    assert res["ok"] is True

    time.sleep(0.3)
    mgr.cancel_all()

    assert len(fired_reminders) == 1
    assert fired_reminders[0].message == "Fast reminder"

    # Status in DB should now be 'fired'
    with sqlite3.connect(str(temp_db)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM reminders WHERE id = ?", (res["id"],))
        assert cur.fetchone()[0] == "fired"


def test_reload_pending_handles_future_and_missed(temp_db: Path, fixed_now: datetime.datetime) -> None:
    """Reloading on restart:
    - If target time is past: marks 'missed' and NEVER fires
    - If target time is future: re-arms timer
    """
    # Pre-populate DB with 1 past pending and 1 future pending
    past_time = fixed_now - datetime.timedelta(hours=2)
    future_time = fixed_now + datetime.timedelta(hours=2)

    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                target_time_iso TEXT NOT NULL,
                target_timestamp REAL NOT NULL,
                created_at_iso TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO reminders VALUES (1, 'Old meeting', ?, ?, ?, 'pending')",
            (past_time.isoformat(), past_time.timestamp(), past_time.isoformat()),
        )
        conn.execute(
            "INSERT INTO reminders VALUES (2, 'Future meeting', ?, ?, ?, 'pending')",
            (future_time.isoformat(), future_time.timestamp(), fixed_now.isoformat()),
        )
        conn.commit()

    due_events = []
    missed_events = []

    mgr = ReminderManager(
        db_path=temp_db,
        on_due=lambda r: due_events.append(r),
        on_missed=lambda r: missed_events.append(r),
    )

    counts = mgr.reload_pending(reference_time=fixed_now)
    mgr.cancel_all()

    assert counts["missed"] == 1
    assert counts["scheduled"] == 1
    assert len(missed_events) == 1
    assert missed_events[0].id == 1
    assert len(due_events) == 0  # Missed one did NOT fire

    # Check DB state
    with sqlite3.connect(str(temp_db)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM reminders ORDER BY id")
        rows = cur.fetchall()
        assert rows == [(1, "missed"), (2, "pending")]
