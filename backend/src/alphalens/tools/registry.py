"""Tool registry.

The registry is intentionally minimal: name → Tool. Each tool is a
callable wrapped with metadata (name, description, parameters). The
agent looks up tools by name and invokes them with kwargs; the result
is a `ToolResult` carrying typed `data` plus a short `summary` string
for use in synthesized reasoning.

An optional `UsageService` can be injected at construction time to
record every tool invocation without changing any call sites.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Output of a tool invocation.

    `data` is the structured payload (typed dataclass or dict) the agent
    can forward as evidence. `summary` is a human-readable one-liner the
    agent can include in its reasoning trace.
    """

    name: str
    summary: str
    data: Any


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    func: Callable[..., ToolResult]
    parameters: dict[str, str] = field(default_factory=dict)

    def __call__(self, **kwargs: Any) -> ToolResult:
        return self.func(**kwargs)


class ToolRegistry:
    def __init__(self, *, usage_service: object | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        # Duck-typed against UsageService; avoids circular imports.
        self._usage = usage_service

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool '{name}'.") from exc

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, /, **kwargs: Any) -> ToolResult:
        result = self.get(name)(**kwargs)
        self._record_tool(name, result, success=True)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_tool(self, name: str, result: ToolResult, *, success: bool) -> None:
        if self._usage is None:
            return
        try:
            provider = (
                result.data.get("provider")
                if isinstance(result.data, dict)
                else None
            )
            metadata: dict[str, Any] = {"summary": result.summary[:120]}
            if isinstance(result.data, dict):
                if "fallback_used" in result.data:
                    metadata["fallback_used"] = bool(result.data.get("fallback_used"))
                if "provider_source" in result.data:
                    metadata["provider_source"] = str(result.data.get("provider_source"))
            self._usage.record_tool_usage(
                tool_name=name,
                success=success,
                provider=provider,
                metadata=metadata,
            )
        except Exception:  # noqa: BLE001 - never let tracking break the agent
            pass
