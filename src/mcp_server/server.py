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

from mcp.server import NotificationOptions, Server  # noqa: E402

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

    async def run() -> None:
        async with server.transport_stdio() as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
