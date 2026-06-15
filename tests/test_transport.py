"""Tests for src/mcp_server/transport.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestRunStdio:
    @pytest.mark.skip(reason="MCP SDK transport_stdio mocking requires real SDK internals")
    @pytest.mark.asyncio
    async def test_run_stdio_calls_server(self):
        from src.mcp_server.transport import run_stdio

        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__.return_value = (MagicMock(), MagicMock())
        mock_server.transport_stdio.return_value = mock_ctx

        await run_stdio(mock_server)

        mock_server.transport_stdio.assert_called_once()
        mock_server.run.assert_called_once()


class TestRunHttp:
    def test_run_http_importable(self):
        from src.mcp_server.transport import run_http

        assert callable(run_http)

    def test_run_http_calls_sse_app(self):
        """Should call server.sse_app()."""
        from src.mcp_server.transport import run_http

        mock_server = MagicMock()
        mock_server.sse_app.return_value = MagicMock()

        with patch("uvicorn.run"):
            run_http(mock_server)

        mock_server.sse_app.assert_called_once()

    @patch("uvicorn.run")
    def test_run_http_defaults(self, mock_uvicorn):
        from src.mcp_server.transport import run_http

        mock_server = MagicMock()
        mock_server.sse_app.return_value = MagicMock()

        run_http(mock_server)

        mock_uvicorn.assert_called_once()
        kw = mock_uvicorn.call_args[1]
        assert kw["host"] == "127.0.0.1"
        assert kw["port"] == 8080

    @patch("uvicorn.run")
    def test_run_http_custom_host_port(self, mock_uvicorn):
        from src.mcp_server.transport import run_http

        mock_server = MagicMock()
        mock_server.sse_app.return_value = MagicMock()

        run_http(mock_server, host="0.0.0.0", port=3000)

        kw = mock_uvicorn.call_args[1]
        assert kw["host"] == "0.0.0.0"
        assert kw["port"] == 3000
