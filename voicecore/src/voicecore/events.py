"""Structured event definitions and thread-safe synchronous EventBus for VoiceCore."""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """Base event carrying run correlation ID and timestamp."""
    run_id: str
    ts: float = field(default_factory=time.time)


@dataclass
class ListeningStartedEvent(Event):
    pass


@dataclass
class ListeningStoppedEvent(Event):
    pass


@dataclass
class NoSpeechEvent(Event):
    pass


@dataclass
class TranscriptEvent(Event):
    text: str = ""
    language: str = "en"
    asr_ms: float = 0.0


@dataclass
class RouteEvent(Event):
    calls: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    nlu_ms: float = 0.0
    reasoning: str = ""
    negation: bool = False
    ungrounded: List[str] = field(default_factory=list)


@dataclass
class GateEvent(Event):
    call: Dict[str, Any] = field(default_factory=dict)
    decision: str = "REFUSE"  # ACT | CONFIRM | REFUSE
    reason: str = ""


@dataclass
class ConfirmRequestEvent(Event):
    call: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultEvent(Event):
    call: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    ms: float = 0.0


@dataclass
class ReminderDueEvent(Event):
    reminder_id: str = ""
    message: str = ""
    when: str = ""


@dataclass
class ErrorEvent(Event):
    stage: str = ""
    error_type: str = ""
    message: str = ""


@dataclass
class DoneEvent(Event):
    total_ms: float = 0.0


class EventBus:
    """Thread-safe synchronous event bus for dispatching VoiceCore events."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[type, List[Callable[[Any], None]]] = {}
        self._all_subscribers: List[Callable[[Event], None]] = []

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Subscribe a handler to a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[Event], None]) -> None:
        """Subscribe a handler to all events dispatched on the bus."""
        with self._lock:
            if handler not in self._all_subscribers:
                self._all_subscribers.append(handler)

    def unsubscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Unsubscribe a handler from a specific event type."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        """Synchronously publish an event to matching subscribers."""
        handlers_to_call: List[Callable[[Any], None]] = []
        with self._lock:
            event_type = type(event)
            if event_type in self._subscribers:
                handlers_to_call.extend(self._subscribers[event_type])
            handlers_to_call.extend(self._all_subscribers)

        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception:
                # Event dispatching must never crash the pipeline
                pass

