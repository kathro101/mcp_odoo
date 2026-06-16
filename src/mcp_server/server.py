"""MCP server entry point.

Thin wrapper around the mcp Python SDK.  ~80 lines.
No business logic here — all delegation to tools.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable regardless of cwd (for Claude Desktop)
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server import Server  # noqa: E402

from .tools import TOOLS, handle_tool_call  # noqa: E402

# ── Server Instance ─────────────────────────────────────────────────────

server = Server("odoo-agent")


@server.list_tools()
async def list_tools() -> list:
    """Return the list of available MCP tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Handle an MCP tool call."""
    return await handle_tool_call(name, arguments)


# ── Entry Point ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server via stdio transport."""
    import asyncio

    from mcp.server.stdio import stdio_server

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
