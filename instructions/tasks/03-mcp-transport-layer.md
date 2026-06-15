# Task: MCP Transport Layer

**Created:** 2026-06-15  
**Status:** 🔴 Not started  
**Priority:** MEDIUM — needed for HTTP dev mode and web UI  
**Depends on:** Phase 4 (mcp_server/server.py, mcp_server/tools.py)

---

## Problem

The MCP server currently only supports stdio transport. For development and testing (and to support the web UI), we need HTTP transport. The rewrite plan calls for a thin `transport.py` module.

## Files to Create

| File                          | Purpose                     |
| ----------------------------- | --------------------------- |
| `src/mcp_server/transport.py` | `run_stdio()`, `run_http()` |
| `tests/test_transport.py`     | 5+ tests                    |

## Specifications

```python
async def run_stdio(server: Server) -> None:
    """Run the MCP server via stdio transport (production mode).

    Used by Claude Desktop. Reads/writes JSON-RPC messages
    over stdin/stdout with Content-Length framing.
    """

async def run_http(server: Server, host: str = "127.0.0.1",
                    port: int = 8080) -> None:
    """Run the MCP server via HTTP transport (dev/testing mode).

    Uses SSE for streaming.  Accessible at http://localhost:8080.
    Useful for web UI integration and debugging.
    """
```

## Test Categories (TDD Required)

1. stdio transport: mock stdin/stdout, verify message framing
2. HTTP transport: start server, send request, verify response
3. HTTP health check endpoint
4. Content-Length framing correctness
5. Server shutdown cleanup

## Acceptance Criteria

- [ ] All tests pass
- [ ] stdio transport works with Claude Desktop config
- [ ] HTTP transport accessible for dev web UI
- [ ] No regression in existing MCP server tests
