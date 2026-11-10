"""set_reminder tool (T1) — schedules local reminders with SQLite persistence.

Design contracts:
- Acceptance: accepts message (str) and when (str).
- Parsing: parses relative offsets ("in 20 minutes", "in 2 hours"), natural expressions
  ("tomorrow at 10", "at 6pm"), and ISO-8601 strings.
- Time representation: Always computes and stores local time WITH its UTC offset
  (e.g., "2026-11-11T10:00:00+05:30").
- Persistence: Stored locally in a SQLite database (default: ~/.voicecore/reminders.db).
- Restart lifecycle: On reload_pending(), past un-triggered reminders are marked "missed"
  and NOT fired. Future reminders are re-scheduled with background timers.
- Operational constraint: Explicitly states that reminders ONLY fire while VYKE is running.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import datetime
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Reminder:
    id: int
    message: str
    target_time_iso: str  # Local ISO 8601 with UTC offset, e.g. "2026-11-11T10:00:00+05:30"
    target_timestamp: float
    created_at_iso: str
    status: str  # "pending", "fired", "missed", "cancelled"


def get_default_db_path() -> Path:
    base = Path.home() / ".voicecore"
    base.mkdir(parents=True, exist_ok=True)
    return base / "reminders.db"


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
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
        conn.commit()


def parse_target_time(
    when_str: str,
    reference_time: Optional[datetime.datetime] = None,
) -> datetime.datetime:
    """Parse natural or ISO time string into a timezone-aware local datetime with UTC offset."""
    if not when_str or not isinstance(when_str, str) or not when_str.strip():
        raise ValueError("Time string cannot be empty")

    now = reference_time or datetime.datetime.now(datetime.timezone.utc).astimezone()
    local_tz = now.tzinfo
    raw = when_str.strip().lower()

    # 1. Relative offset: "in N minutes|hours|days|seconds"
    m_rel = re.match(r"^in\s+(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|s|sec|secs|second|seconds)?$", raw)
    if m_rel:
        val = int(m_rel.group(1))
        unit = m_rel.group(2) or "minutes"
        if unit.startswith("s"):
            delta = datetime.timedelta(seconds=val)
        elif unit.startswith("h"):
            delta = datetime.timedelta(hours=val)
        elif unit.startswith("d"):
            delta = datetime.timedelta(days=val)
        else:
            delta = datetime.timedelta(minutes=val)
        return now + delta

    # 2. "tomorrow at HH[:MM]" or "tomorrow HH[:MM]"
    m_tom = re.match(r"^tomorrow(?:\s+at)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", raw)
    if m_tom:
        hour = int(m_tom.group(1))
        minute = int(m_tom.group(2) or 0)
        ampm = m_tom.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        tomorrow_date = now.date() + datetime.timedelta(days=1)
        return datetime.datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, hour, minute, 0, tzinfo=local_tz)

    # 3. "today at HH[:MM]" or "at HH[:MM]"
    m_at = re.match(r"^(?:today\s+at|at)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", raw)
    if m_at and (m_at.group(3) or ":" in raw or raw.startswith("at") or raw.startswith("today")):
        hour = int(m_at.group(1))
        minute = int(m_at.group(2) or 0)
        ampm = m_at.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        candidate = datetime.datetime(now.year, now.month, now.day, hour, minute, 0, tzinfo=local_tz)
        if candidate <= now:
            # If time has passed today, assume tomorrow
            candidate += datetime.timedelta(days=1)
        return candidate

    # 4. Partial needle output like "2026-11-11 10" or "2026-11-11 10:00"
    m_needle_date = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2})(?::(\d{2}))?$", raw)
    if m_needle_date:
        year = int(m_needle_date.group(1))
        month = int(m_needle_date.group(2))
        day = int(m_needle_date.group(3))
        hour = int(m_needle_date.group(4))
        minute = int(m_needle_date.group(5) or 0)
        return datetime.datetime(year, month, day, hour, minute, 0, tzinfo=local_tz)

    # 5. Full ISO 8601 parse attempt
    try:
        dt = datetime.datetime.fromisoformat(when_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz)
        return dt
    except ValueError:
        pass

    raise ValueError(f"Unable to parse time expression: '{when_str}'")


class ReminderManager:
    """Manages reminder persistence, active timers, reload-on-restart, and missed reminders."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        on_due: Optional[Callable[[Reminder], None]] = None,
        on_missed: Optional[Callable[[Reminder], None]] = None,
    ) -> None:
        self.db_path = db_path or get_default_db_path()
        init_db(self.db_path)
        self.on_due = on_due
        self.on_missed = on_missed
        self._timers: Dict[int, threading.Timer] = {}
        self._lock = threading.Lock()

    def set_reminder(
        self,
        message: str,
        when: str,
        reference_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """Create and schedule a reminder.

        Operational notice: Reminders only fire while VYKE is running.
        """
        if not message or not isinstance(message, str) or not message.strip():
            return {"ok": False, "error": "empty_message", "message": "Reminder message cannot be empty."}

        try:
            target_dt = parse_target_time(when, reference_time=reference_time)
        except ValueError as ve:
            return {"ok": False, "error": "invalid_time", "message": str(ve)}

        now = reference_time or datetime.datetime.now(datetime.timezone.utc).astimezone()
        if target_dt <= now:
            return {
                "ok": False,
                "error": "past_time",
                "message": f"Target time '{target_dt.isoformat()}' is in the past.",
            }

        target_iso = target_dt.isoformat()
        target_ts = target_dt.timestamp()
        created_iso = now.isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reminders (message, target_time_iso, target_timestamp, created_at_iso, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (message.strip(), target_iso, target_ts, created_iso),
            )
            reminder_id = cursor.lastrowid
            conn.commit()

        reminder = Reminder(
            id=reminder_id,
            message=message.strip(),
            target_time_iso=target_iso,
            target_timestamp=target_ts,
            created_at_iso=created_iso,
            status="pending",
        )

        # Schedule timer
        delay_s = max(0.0, target_ts - now.timestamp())
        self._arm_timer(reminder, delay_s)

        return {
            "ok": True,
            "id": reminder_id,
            "message": reminder.message,
            "when": reminder.target_time_iso,
            "seconds_until": round(delay_s, 1),
            "notice": "Reminders only fire while VYKE is running.",
        }

    def _arm_timer(self, reminder: Reminder, delay_s: float) -> None:
        def _fire() -> None:
            with self._lock:
                self._timers.pop(reminder.id, None)
            self._mark_status(reminder.id, "fired")
            if self.on_due:
                try:
                    self.on_due(reminder)
                except Exception:
                    pass

        t = threading.Timer(delay_s, _fire)
        t.daemon = True
        with self._lock:
            self._timers[reminder.id] = t
            t.start()

    def _mark_status(self, reminder_id: int, status: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id))
            conn.commit()

    def reload_pending(
        self,
        reference_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, int]:
        """Reload pending reminders from SQLite upon startup.

        Missed reminder policy:
        If target_timestamp is in the past, status is updated to 'missed' and the reminder
        does NOT fire (avoiding stale alert bursts on restart).
        If in the future, a timer is armed for the remaining duration.

        Operational notice: Reminders only fire while VYKE is running.
        """
        now = reference_time or datetime.datetime.now(datetime.timezone.utc).astimezone()
        now_ts = now.timestamp()

        missed_count = 0
        scheduled_count = 0

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminders WHERE status = 'pending'")
            rows = cursor.fetchall()

            for r in rows:
                rem = Reminder(
                    id=r["id"],
                    message=r["message"],
                    target_time_iso=r["target_time_iso"],
                    target_timestamp=r["target_timestamp"],
                    created_at_iso=r["created_at_iso"],
                    status=r["status"],
                )
                if rem.target_timestamp <= now_ts:
                    conn.execute("UPDATE reminders SET status = 'missed' WHERE id = ?", (rem.id,))
                    missed_count += 1
                    if self.on_missed:
                        try:
                            self.on_missed(rem)
                        except Exception:
                            pass
                else:
                    delay_s = max(0.0, rem.target_timestamp - now_ts)
                    self._arm_timer(rem, delay_s)
                    scheduled_count += 1
            conn.commit()

        return {"scheduled": scheduled_count, "missed": missed_count}

    def cancel_all(self) -> None:
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()


# Default singleton instance for tool registry binding
_default_manager: Optional[ReminderManager] = None


def get_default_manager() -> ReminderManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ReminderManager()
    return _default_manager


def set_reminder(message: str, when: str) -> Dict[str, Any]:
    """Set a reminder with a text note at a specified future date or time.

    Parameters:
        message: The reminder note or description to remember.
        when: A natural relative offset, clock time, or ISO-8601 timestamp.

    Reminders only fire while VYKE is running.
    """
    mgr = get_default_manager()
    return mgr.set_reminder(message=message, when=when)


def set_reminder_precheck(
    args: Dict[str, Any],
    reference_time: Optional[datetime.datetime] = None,
) -> tuple[bool, str]:
    """Pre-check for set_reminder: when must parse to a future time, and message non-empty."""
    message = args.get("message")
    if not message or not isinstance(message, str) or not message.strip():
        return False, "Reminder message cannot be empty."

    when = args.get("when")
    if not when or not isinstance(when, str) or not when.strip():
        return False, "Reminder time expression ('when') cannot be empty."

    try:
        target_dt = parse_target_time(when, reference_time=reference_time)
    except ValueError as ve:
        return False, f"Invalid time expression: {ve}"

    now = reference_time or datetime.datetime.now(datetime.timezone.utc).astimezone()
    if target_dt <= now:
        return False, f"Target time '{target_dt.isoformat()}' is in the past."

    return True, ""

