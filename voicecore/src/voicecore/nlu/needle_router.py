"""Needle 3 router implementation wrapping Cactus Compute."""
from __future__ import annotations

import time
from typing import Any, Callable, List, Optional

from voicecore.engine import NeedleAgent, tool as engine_tool
from voicecore.nlu.base import RouteResult, Router, ToolCall
from voicecore.tools.registry import ToolRegistry


class NeedleRouter(Router):
    """NLU router using local Needle 3 model with grammar-constrained tool calling."""

    def __init__(
        self,
        registry: ToolRegistry,
        weights: Optional[str] = None,
        stateless: bool = True,
    ) -> None:
        self.registry = registry
        self.stateless = stateless

        raw_funcs = self.registry.get_functions()
        # Ensure functions are decorated with engine @tool if not already
        engine_tools = []
        for fn in raw_funcs:
            if not hasattr(fn, "__tool__"):
                # Decorate with engine_tool
                decorated = engine_tool(fn)
                engine_tools.append(decorated)
            else:
                engine_tools.append(fn)

        self._agent = NeedleAgent(
            tools=engine_tools,
            weights=weights,
            stateless=self.stateless,
        )

    def route(self, text: str) -> RouteResult:
        """Parse natural language text using Needle 3 complete()."""
        t0 = time.perf_counter()

        if not text or not text.strip():
            return RouteResult(
                calls=[],
                confidence=0.0,
                nlu_ms=0.0,
                reasoning="Empty query",
                negation=False,
                ungrounded=[],
            )

        out = self._agent.complete(text.strip())
        nlu_ms = (time.perf_counter() - t0) * 1000.0

        val = out.get("validation", {})
        raw_calls = out.get("function_calls", [])
        confidence = float(out.get("confidence", 0.0))
        reasoning = out.get("reasoning", "")
        negation = bool(val.get("negation", False))
        ungrounded = list(val.get("ungrounded", []))

        calls = [
            ToolCall(
                name=c["name"],
                arguments=dict(c.get("arguments", {})),
            )
            for c in raw_calls
            if isinstance(c, dict) and "name" in c
        ]

        return RouteResult(
            calls=calls,
            confidence=confidence,
            nlu_ms=nlu_ms,
            reasoning=reasoning,
            negation=negation,
            ungrounded=ungrounded,
        )

    def close(self) -> None:
        """Release agent resources."""
        if hasattr(self, "_agent") and self._agent is not None:
            self._agent.close()

    def __enter__(self) -> NeedleRouter:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
