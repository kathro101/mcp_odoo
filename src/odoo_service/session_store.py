"""Session state management.

Simple dict-based key-value store for conversation state.  Keyed by
session_id.  The MCP client (Claude) manages the conversation flow;
we just remember which agent/model we're working with per session.

No database, no persistence — sessions live in memory for the lifetime
of the MCP server process.
"""

from __future__ import annotations

from src.shared.types import SessionState


class SessionStore:
    """In-memory session state store.

    Each session tracks: current agent, current model, pending operation,
    and an arbitrary context dict for multi-turn workflows.
    """

    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def get_state(self, session_id: str) -> SessionState:
        """Get or create the session state for the given ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            The existing or newly created SessionState.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def set_state(self, session_id: str, state: SessionState) -> None:
        """Store a session state.

        Args:
            session_id: Unique session identifier.
            state: The SessionState to store.
        """
        state.session_id = session_id
        self._sessions[session_id] = state

    def get_last_agent(self, session_id: str) -> str:
        """Get the last agent used in this session.

        Args:
            session_id: Unique session identifier.

        Returns:
            The agent key, or empty string if not set.
        """
        state = self.get_state(session_id)
        return state.current_agent

    def set_last_agent(self, session_id: str, agent_key: str) -> None:
        """Set the current agent for this session.

        Args:
            session_id: Unique session identifier.
            agent_key: The agent key to set.
        """
        state = self.get_state(session_id)
        state.current_agent = agent_key

    def reset_state(self, session_id: str) -> None:
        """Clear the state for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._sessions.pop(session_id, None)
