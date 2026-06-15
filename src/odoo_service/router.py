"""Keyword-based agent routing.

Pure function — no LLM, no state.  Scores agents by cumulative keyword
match length against the user's message.  Higher score = better match.

This replaces the old AgentCouncil + CSOrchestrator routing logic that
used LLM-based intent classification.
"""

from __future__ import annotations

from src.shared.types import AgentConfig, RouteResult


def route_message(message: str, agents: dict[str, AgentConfig]) -> RouteResult:
    """Route a user message to the best-matching agent.

    For each agent, counts how many of its keywords appear in the message
    (case-insensitive substring match).  The agent with the highest total
    keyword-length score wins.

    Args:
        message: The user's natural language message.
        agents: Dict of agent_key -> AgentConfig.

    Returns:
        RouteResult with the best agent_key, its default_model, and score.
        If no keywords match at all, returns RouteResult(None, None, 0).
    """
    if not message or not agents:
        return RouteResult(agent_key=None, model_key=None, score=0)

    text = message.lower()
    best: RouteResult = RouteResult(agent_key=None, model_key=None, score=0)

    for agent in agents.values():
        score = 0
        for keyword in agent.keywords:
            if keyword.lower() in text:
                score += len(keyword)

        if score > best.score or (
            score == best.score
            and best.agent_key is not None
            and agent.key < best.agent_key
        ):
            best = RouteResult(
                agent_key=agent.key,
                model_key=agent.default_model,
                score=score,
            )

    return best
