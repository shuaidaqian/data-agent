"""声明式 Agent 工具注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class ToolSpec:
    """Agent 工具的声明式定义。"""

    name: str
    description: str
    fn: Callable[..., Any]
    parameters: Dict[str, str] = field(default_factory=dict)
    category: str = "general"
    permission_scope: str = "none"
    requires_sql_safety: bool = False
    timeout_ms: int = 10000


class ToolRegistry:
    """集中注册和导出现有 Agent 可调用工具。"""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        """注册工具，工具名必须唯一。"""
        if spec.name in self._tools:
            raise ValueError(f"工具 `{spec.name}` 已注册")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec:
        """按名称获取工具定义。"""
        return self._tools[name]

    def names(self) -> List[str]:
        """按注册顺序返回工具名。"""
        return list(self._tools.keys())

    def specs(self) -> List[ToolSpec]:
        """按注册顺序返回工具定义。"""
        return list(self._tools.values())

    def as_tool_defs(self):
        """导出为旧 Agent 实现仍在使用的 ToolDef。"""
        from sql_agent.agent.tools import ToolDef

        return [
            ToolDef(
                name=spec.name,
                description=spec.description,
                fn=spec.fn,
                parameters=spec.parameters,
            )
            for spec in self.specs()
        ]
