"""Agent tools.

A `Tool` bundles a name, description, JSON-schema-ish parameter spec, and
a callable. Tools are registered in a `ToolRegistry` so the agent can
look them up by name and invoke them uniformly.
"""

from __future__ import annotations

from alphalens.tools.registry import Tool, ToolRegistry, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolResult"]
