"""Explicit tool registry with tier assignments and schema export."""
from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from typing import Any, Callable, Dict, List, Optional


VALID_TIERS = {"T0", "T1", "T2"}


@dataclass
class ToolDefinition:
    """Metadata and execution handle for a registered tool."""
    name: str
    description: str
    tier: str  # T0, T1, T2
    fn: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """Registry managing tool lifecycle, risk tiers, and execution boundaries."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        fn: Callable[..., Any],
        tier: str = "T1",
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ToolDefinition:
        """Register a Python callable as an authorized VoiceCore tool."""
        if tier not in VALID_TIERS:
            raise ValueError(f"Invalid tier '{tier}'. Must be one of {VALID_TIERS}")

        tool_name = name or fn.__name__
        if name and hasattr(fn, "__name__") and fn.__name__ != name:
            try:
                fn.__name__ = name
            except (AttributeError, TypeError):
                pass
        tool_desc = (description or inspect.getdoc(fn) or "").strip()

        sig = inspect.signature(fn)
        params: Dict[str, Any] = {}
        for p_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            params[p_name] = {
                "type": param_type,
                "default": None if param.default is inspect.Parameter.empty else param.default,
            }

        definition = ToolDefinition(
            name=tool_name,
            description=tool_desc,
            tier=tier,
            fn=fn,
            parameters=params,
        )
        self._tools[tool_name] = definition
        return definition

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Lookup tool definition by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if tool name is registered."""
        return name in self._tools

    def get_tier(self, name: str) -> Optional[str]:
        """Get the risk tier for a tool."""
        definition = self.get(name)
        return definition.tier if definition else None

    def list_tools(self) -> List[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def get_functions(self) -> List[Callable[..., Any]]:
        """Return raw callable functions (for engine binding)."""
        return [td.fn for td in self._tools.values()]

    def export_schema(self) -> List[Dict[str, Any]]:
        """Export standardized JSON schema for all registered tools."""
        schemas = []
        for td in self._tools.values():
            schemas.append({
                "name": td.name,
                "description": td.description,
                "tier": td.tier,
                "parameters": td.parameters,
            })
        return schemas

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Safely execute a tool with isolation.
        
        Guarantees:
        - Never raises exceptions to caller; returns {'ok': False, 'error': ...}
        - Validates tool presence
        """
        td = self.get(name)
        if not td:
            return {"ok": False, "error": f"Tool '{name}' is not registered"}

        try:
            res = td.fn(**arguments)
            if isinstance(res, dict):
                if "ok" not in res:
                    res["ok"] = True
                return res
            return {"ok": True, "result": res}
        except TypeError as te:
            return {"ok": False, "error": f"Invalid arguments for '{name}': {te}"}
        except Exception as e:
            return {"ok": False, "error": f"Execution error in '{name}': {type(e).__name__}: {e}"}
