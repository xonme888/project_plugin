#!/usr/bin/env python3
"""FastMCP stdio server for LoaRing Product Ops."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import Tool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.mcp_schema import TOOLS  # noqa: E402
from loaring_ops.mcp_tools import call_tool  # noqa: E402


class LoaringTool(Tool):
    async def run(self, arguments: dict[str, Any]) -> Any:
        return self.convert_result(call_tool(self.name, arguments))


def build_server() -> FastMCP:
    server = FastMCP(name="loaring-product-ops", version="0.1.4")
    for name, definition in TOOLS.items():
        server.add_tool(
            LoaringTool(
                name=name,
                description=definition["description"],
                parameters=definition["inputSchema"],
            )
        )
    return server


def main() -> int:
    build_server().run(transport="stdio", show_banner=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
