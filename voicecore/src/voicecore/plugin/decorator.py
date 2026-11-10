"""Decorator for defining host tools in the VoiceCore plugin system."""
from __future__ import annotations

import functools
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


def tool(
    fn: Optional[Callable[..., Any]] = None,
    *,
    tier: Optional[str] = None,
    precheck: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None,
    triggers: Optional[List[str]] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Any:
    """Decorator to mark and configure a Python function as a VoiceCore host tool.

    Usage:
        @tool
        def start_focus(minutes: int):
            \"\"\"Start focus mode.\"\"\"
            ...

        @tool(tier="T0", precheck=check_query, triggers=["find", "locate"])
        def find_item(name: str):
            ...
    """
    def decorator(target_fn: Callable[..., Any]) -> Callable[..., Any]:
        setattr(target_fn, "_voicecore_tier", tier)
        setattr(target_fn, "_voicecore_precheck", precheck)
        setattr(target_fn, "_voicecore_triggers", triggers)
        setattr(target_fn, "_voicecore_name", name)
        setattr(target_fn, "_voicecore_description", description)
        setattr(target_fn, "_voicecore_is_host", True)
        return target_fn

    if fn is not None:
        # Used as @tool without parenthesis
        return decorator(fn)
    return decorator
