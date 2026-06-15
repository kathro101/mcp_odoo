"""Shared dataclasses for the Odoo AI Agent.

All structured data that crosses module boundaries is defined here as
dataclasses, not dicts.  Uses Python 3.10+ syntax (X | Y unions, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FieldInfo:
    """Metadata for a single Odoo model field.

    Extracted deterministically from ir.model.fields + fields_get().
    Zero AI tokens involved.
    """

    name: str
    field_type: str
    string: str
    required: bool = False
    readonly: bool = False
    store: bool = True
    computed: bool = False
    related: str = ""
    relation: str = ""
    selection: list[tuple[str, str]] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    usage_frequency: int = 0
    help_text: str = ""


@dataclass
class SubModelSchema:
    """Metadata for a sub-model relationship (one2many / many2one)."""

    field_name: str
    related_model: str
    relation_field: str = ""
    is_one_to_many: bool = False


@dataclass
class ModelSchema:
    """Full schema for an Odoo model — fields, aliases, keywords.

    One instance per Odoo model. Serialized to config/schemas/<key>.json.
    """

    key: str
    label: str
    odoo_model: str
    all_fields: dict[str, FieldInfo]
    summary: str = ""
    create_fields: list[str] = field(default_factory=list)
    search_fields: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    field_aliases: dict[str, str] = field(default_factory=dict)
    match_keywords: list[str] = field(default_factory=list)
    sub_models: list[SubModelSchema] = field(default_factory=list)
    usage_frequency_total: int = 0
    workflow_hints: str = ""


@dataclass
class AgentConfig:
    """Configuration for an agent persona.

    Loaded from config/agents.json.  Agents route user messages to
    specific Odoo models based on keyword matching (no LLM needed).
    """

    key: str
    name: str
    description: str
    keywords: list[str]
    models: list[str] = field(default_factory=list)
    default_model: str | None = None


@dataclass
class SessionState:
    """Conversation state for a single session.

    Stored in a simple key-value store keyed by session_id.
    The MCP client (Claude) manages conversation flow; we just
    remember which agent/model we're working with.
    """

    session_id: str = ""
    current_agent: str = ""
    current_model: str = ""
    pending_operation: str = ""
    context: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class RouteResult:
    """Result of keyword-based routing.

    score > 0 means a match was found.  Higher score = better match.
    """

    agent_key: str | None
    model_key: str | None
    score: int
