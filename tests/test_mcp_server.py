"""Tests for src/mcp_server/tools.py — MCP tool definitions and handlers."""

from __future__ import annotations

from unittest.mock import patch


class TestToolDefinitions:
    """Tests for tool definition constants."""

    def test_chat_odoo_tool_defined(self):
        """TOOLS should include chat_odoo with correct schema."""
        from src.mcp_server.tools import TOOLS

        chat_tool = next(t for t in TOOLS if t.name == "chat_odoo")
        assert chat_tool.name == "chat_odoo"
        props = chat_tool.inputSchema.get("properties", {})
        assert "message" in props
        assert props["message"]["type"] == "string"
        assert "action" in props
        assert "session_id" in props
        assert "params" in props

    def test_list_models_tool_defined(self):
        """TOOLS should include list_models."""
        from src.mcp_server.tools import TOOLS

        list_tool = next(t for t in TOOLS if t.name == "list_models")
        assert list_tool.name == "list_models"

    def test_list_agents_tool_defined(self):
        """TOOLS should include list_agents."""
        from src.mcp_server.tools import TOOLS

        agents_tool = next(t for t in TOOLS if t.name == "list_agents")
        assert agents_tool.name == "list_agents"

    def test_exactly_three_tools(self):
        """Should have exactly 3 tools: chat_odoo, list_models, list_agents."""
        from src.mcp_server.tools import TOOLS

        tool_names = {t.name for t in TOOLS}
        assert tool_names == {"chat_odoo", "list_models", "list_agents"}


class TestHandleToolCall:
    """Tests for handle_tool_call dispatcher."""

    @patch("src.mcp_server.tools.chat_odoo_handler")
    async def test_chat_odoo_dispatches(self, mock_handler):
        """handle_tool_call should dispatch chat_odoo to its handler."""
        from src.mcp_server.tools import handle_tool_call

        mock_handler.return_value = [{"type": "text", "text": "Hello!"}]

        result = await handle_tool_call("chat_odoo", {"message": "Hello", "session_id": "abc"})

        mock_handler.assert_called_once_with(message="Hello", session_id="abc")
        assert result[0]["type"] == "text"

    @patch("src.mcp_server.tools.list_models_handler")
    async def test_list_models_dispatches(self, mock_handler):
        """handle_tool_call should dispatch list_models."""
        from src.mcp_server.tools import handle_tool_call

        mock_handler.return_value = [{"type": "text", "text": "Models: ..."}]

        result = await handle_tool_call("list_models", {})

        mock_handler.assert_called_once()
        assert len(result) > 0

    @patch("src.mcp_server.tools.list_agents_handler")
    async def test_list_agents_dispatches(self, mock_handler):
        """handle_tool_call should dispatch list_agents."""
        from src.mcp_server.tools import handle_tool_call

        mock_handler.return_value = [{"type": "text", "text": "Agents: ..."}]

        result = await handle_tool_call("list_agents", {})

        mock_handler.assert_called_once()
        assert len(result) > 0

    async def test_unknown_tool_returns_error(self):
        """handle_tool_call should return error for unknown tool names."""
        from src.mcp_server.tools import handle_tool_call

        result = await handle_tool_call("unknown_tool", {})

        assert result[0]["type"] == "text"
        assert "Unknown tool" in result[0]["text"]
