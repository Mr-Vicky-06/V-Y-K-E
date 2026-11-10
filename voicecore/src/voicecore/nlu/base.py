"""NLU router protocol and data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class ToolCall:
    """Represents a structured tool call proposed by the NLU engine."""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """Result of intent routing."""
    calls: List[ToolCall] = field(default_factory=list)
    confidence: float = 0.0
    nlu_ms: float = 0.0
    reasoning: str = ""
    negation: bool = False
    ungrounded: List[str] = field(default_factory=list)


class Router(Protocol):
    """Protocol for intent routing and parameter extraction implementations."""

    def route(self, text: str) -> RouteResult:
        """Parse natural language text and return ordered tool calls with confidence."""
        ...

