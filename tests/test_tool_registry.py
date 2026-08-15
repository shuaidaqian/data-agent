from __future__ import annotations

import pytest

from sql_agent.agent.tools import ToolResult
from sql_agent.runtime.tool_registry import ToolRegistry, ToolSpec


def _ok_tool(_: str = "") -> ToolResult:
    return ToolResult(output="ok")


def test_tool_registry_registers_declarative_tool_specs():
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="SqlDbQuery",
            description="执行只读 SQL 查询",
            fn=_ok_tool,
            parameters={"query": "SQL 查询语句"},
            category="sql",
            permission_scope="database:read",
            requires_sql_safety=True,
            timeout_ms=5000,
        )
    )

    spec = registry.get("SqlDbQuery")

    assert spec.name == "SqlDbQuery"
    assert spec.permission_scope == "database:read"
    assert spec.requires_sql_safety is True
    assert spec.timeout_ms == 5000
    assert registry.names() == ["SqlDbQuery"]


def test_tool_registry_rejects_duplicate_tool_names():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="SystemTime", description="获取系统时间", fn=_ok_tool))

    with pytest.raises(ValueError, match="SystemTime"):
        registry.register(ToolSpec(name="SystemTime", description="重复工具", fn=_ok_tool))


def test_tool_registry_exports_legacy_tool_defs_for_existing_agents():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="SystemTime", description="获取系统时间", fn=_ok_tool))

    tool_defs = registry.as_tool_defs()

    assert len(tool_defs) == 1
    assert tool_defs[0].name == "SystemTime"
    assert tool_defs[0].fn("").output == "ok"
