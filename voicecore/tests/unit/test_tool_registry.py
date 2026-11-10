import pytest
from voicecore.tools.registry import ToolRegistry, ToolDefinition


def test_registry_register_and_lookup():
    reg = ToolRegistry()

    def sample_tool(query: str, limit: int = 5) -> dict:
        """Search query with limit."""
        return {"query": query, "limit": limit}

    td = reg.register(sample_tool, tier="T0", name="search")
    assert td.name == "search"
    assert td.tier == "T0"
    assert td.description == "Search query with limit."
    assert "query" in td.parameters
    assert td.parameters["query"]["type"] == "string"
    assert td.parameters["limit"]["type"] == "integer"
    assert td.parameters["limit"]["default"] == 5

    assert reg.has("search")
    assert reg.get_tier("search") == "T0"
    assert not reg.has("nonexistent")


def test_registry_rejects_invalid_tier():
    reg = ToolRegistry()

    def dummy():
        pass

    with pytest.raises(ValueError, match="Invalid tier"):
        reg.register(dummy, tier="T9")


def test_registry_export_schema():
    reg = ToolRegistry()

    def tool_a(x: str):
        """Tool A doc."""
        return {"x": x}

    reg.register(tool_a, tier="T1")
    schema = reg.export_schema()

    assert len(schema) == 1
    assert schema[0]["name"] == "tool_a"
    assert schema[0]["tier"] == "T1"
    assert schema[0]["description"] == "Tool A doc."
    assert "x" in schema[0]["parameters"]


def test_registry_safe_execution_success():
    reg = ToolRegistry()

    def add(a: int, b: int) -> dict:
        return {"sum": a + b}

    reg.register(add, tier="T1")
    res = reg.execute("add", {"a": 2, "b": 3})
    assert res["ok"] is True
    assert res["sum"] == 5


def test_registry_safe_execution_unregistered():
    reg = ToolRegistry()
    res = reg.execute("missing_tool", {})
    assert res["ok"] is False
    assert "not registered" in res["error"]


def test_registry_safe_execution_catches_type_error():
    reg = ToolRegistry()

    def strict_fn(required_arg: str):
        return {"res": required_arg}

    reg.register(strict_fn, tier="T1")
    # Missing required argument
    res = reg.execute("strict_fn", {})
    assert res["ok"] is False
    assert "Invalid arguments" in res["error"]


def test_registry_safe_execution_catches_runtime_exception():
    reg = ToolRegistry()

    def buggy():
        raise ZeroDivisionError("division by zero in tool")

    reg.register(buggy, tier="T1")
    res = reg.execute("buggy", {})
    assert res["ok"] is False
    assert "ZeroDivisionError" in res["error"]

