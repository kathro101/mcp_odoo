"""MCP server transport helpers.

Provides stdio (production) and HTTP+SSE (dev/testing) transport modes.
"""

from __future__ import annotations


async def run_stdio(server) -> None:
    """Run the MCP server via stdio transport (production mode).

    Used by Claude Desktop. Reads/writes JSON-RPC messages
    over stdin/stdout with Content-Length framing.
    """
    async with server.transport_stdio() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


def run_http(server, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the MCP server via HTTP + SSE transport (dev/testing mode).

    Uses the MCP SDK's built-in SSE ASGI app served via uvicorn.
    Accessible at http://localhost:8080 with endpoints /sse and /messages.

    Args:
        server: MCP Server instance.
        host: Bind address (default 127.0.0.1).
        port: Bind port (default 8080).
    """
    import uvicorn

    sse_app = server.sse_app()
    uvicorn.run(sse_app, host=host, port=port, log_level="info")
