# Odoo AI Agent — Complete Rewrite Plan

> **Author:** Senior Software Developer
> **Date:** 2026-06-15
> **Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Audit](#2-current-architecture-audit)
3. [Target Architecture](#3-target-architecture)
4. [Tech Stack Review for MCP](#4-tech-stack-review-for-mcp)
5. [Refactoring Plan — Layer by Layer](#5-refactoring-plan)
6. [AI Strategy — Single AI, No Internal Engine](#6-ai-strategy)
7. [Documentation & GitHub/AI Agent Handling](#7-documentation--github-ai-agent-handling)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Executive Summary

The current codebase (~15,000 lines of Python across 30+ files) has organically grown from a single-file chatbot into a multi-layered system with MCP server, agent council, schema discovery, vector stores, plugins, and a desktop app. While functional, it suffers from:

- **Tight coupling** between layers (e.g. `AgentConversation` imports 20+ modules)
- **Duplicate code paths** (`_get_assistant` exists in both `crew_council.py` and `cs_orchestrator.py`)
- **Fragile model key resolution** (hardcoded `_DEFAULT_MODEL_KEY`, missing fallbacks)
- **Internal LLM engine that competes with MCP's LLM** (two AI brains when one suffices)
- **Complex 3-layer model config merge** (baseline + discovered + curated)

The goal: **a clean, maintainable, testable codebase that uses the MCP client's AI (Claude) as the ONLY AI brain.**

---

## 2. Current Architecture Audit

### 2.1 Size Breakdown

| Area                                  | Files | Lines   | Complexity                | Keep?           |
| ------------------------------------- | ----- | ------- | ------------------------- | --------------- |
| `odoo_agent/conversation.py`          | 1     | 1,383   | ⚠️ Very high — God class  | Refactor        |
| `odoo_agent/cs_orchestrator.py`       | 1     | 982     | ⚠️ High — multi-role      | Simplify        |
| `odoo_agent/schema_discovery.py`      | 1     | 1,361   | ⚠️ High — AI enrichment   | Extract modules |
| `odoo_agent/plugins/ops_logistics.py` | 1     | 1,442   | ⚠️ Highest — domain logic | Split           |
| `odoo_agent/mcp/server.py`            | 1     | 468     | Medium                    | Clean up        |
| `odoo_agent/mcp/tools.py`             | 1     | 342     | Low                       | Clean up        |
| `odoo_agent/crew_council.py`          | 1     | 195     | Low                       | Merge           |
| `odoo_agent/agent_council.py`         | 1     | 585     | Medium                    | Simplify        |
| `odoo_agent/model_config.py`          | 1     | 456     | Medium                    | Simplify        |
| `odoo_agent/prompt_builder.py`        | 1     | 506     | Medium                    | Simplify        |
| `model_configs/model_configs.json`    | 1     | 30,000+ | ⚠️ Massive JSON           | Split           |

### 2.2 Architecture Diagram (Current)

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Desktop / Web UI / Teams Bot                        │
├─────────────────────────────────────────────────────────────┤
│  MCP Server Layer (server.py + tools.py)                   │
│    chat_odoo | search_odoo | analytics_odoo | ...          │
├─────────────────────────────────────────────────────────────┤
│  CrewCouncil → CSOrchestrator                               │
│    ├── AgentCouncil (keyword + LLM routing)                 │
│    ├── AgentConversation (per-model AI engine) ← ❌ Internal LLM       │
│    │     ├── CreateEngine / SearchEngine / DeleteEngine    │
│    │     ├── SchemaDiscovery (AI enrichment)               │
│    │     ├── RAG (Chroma/JSON/PGVector)                    │
│    │     ├── MemoryManager (LangMem-style)                 │
│    │     ├── PromptBuilder                                 │
│    │     └── ContextProvider                               │
│    └── PluginRegistry (domain-specific hooks)              │
├─────────────────────────────────────────────────────────────┤
│  Odoo RPC Layer                                            │
│  Model Config (3-layer merge: baseline+discovered+curated) │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Problems Identified

| #   | Problem                                                                                          | Impact                                                  |
| --- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| 1   | **Two AI brains** — `AgentConversation` has its own LLM pipeline; MCP client also has an LLM     | Confusion, token waste, double cost                     |
| 2   | `AgentConversation` is a **1383-line God class** doing too many things                           | Hard to test, hard to change                            |
| 3   | **Duplicate `_get_assistant`** in `crew_council.py` and `cs_orchestrator.py`                     | Maintenance nightmare                                   |
| 4   | **`model_configs.json` is 30,000+ lines** in a single file                                       | Unmanageable, slow to load                              |
| 5   | **SchemaDiscovery shells out to `gh copilot`** with no clean API fallback                        | Rate-limit issues (recently fixed with Claude fallback) |
| 6   | **Plugin system is tightly coupled** to specific Odoo modules (`ops_logistics.py` is 1442 lines) | Not truly pluggable                                     |
| 7   | **No clear separation** between "MCP tool handlers" and "business logic"                         | All mixed in `tools.py`                                 |

---

## 3. Target Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Claude Desktop / MCP Client                                     │
│  (THE AI BRAIN — all NLP, intent parsing, response generation)   │
├──────────────────────────────────────────────────────────────────┤
│  MCP Server Layer (thin, stateless JSON-RPC bridge)              │
│    ┌──────────────────────────────────────────────────────┐     │
│    │  chat_odoo   — pass message → Odoo → return result    │     │
│    │  list_models — enumerate known schema                 │     │
│    │  list_agents — enumerate agent personas               │     │
│    └──────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  Odoo Service Layer (pure Python, no AI, testable)               │
│    ┌──────────────────────────────────────────────────────┐     │
│    │  Router       — keyword-based agent/model dispatch    │     │
│    │  SchemaStore  — cached model metadata                 │     │
│    │  OdooClient   — XML-RPC wrapper                       │     │
│    │  SessionStore — conversation state per session         │     │
│    └──────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  Odoo XML-RPC                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **No internal LLM** — The MCP client (Claude) is the ONLY AI. Our job is to give it well-structured data and well-defined tools.
2. **Stateless tools** — Each MCP tool call is independent. Session state is stored in a simple key-value store keyed by `session_id`.
3. **Thin tool layer** — Tools are simple Python functions that call the service layer. No business logic in tool handlers.
4. **Flat config** — One `config.json`. Model schemas are cached JSON files, not a 30K-line monolith.
5. **Testable** — Every service layer function is a pure function or has minimal side effects.

---

## 4. Tech Stack Review for MCP

### 4.1 Current Stack

| Component            | Technology                         | Assessment                                                         |
| -------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| MCP Server Transport | Flask HTTP + stdio ndjson          | ✅ Works, but needs Content-Length framing for spec compliance     |
| MCP Protocol         | Manual JSON-RPC 2.0                | ⚠️ Should use `mcp` Python SDK for type safety                     |
| Odoo RPC             | `xmlrpc.client` (stdlib)           | ✅ Good — no dependencies                                          |
| LLM Integration      | `anthropic` SDK + `gh copilot` CLI | ⚠️ Should only be used for schema enrichment, not for runtime chat |
| Vector Database      | Chroma / PGVector / JSON           | ⚠️ Overkill for schema retrieval — use simple JSON index           |
| Desktop App          | PyInstaller + tkinter wizard       | ⚠️ tkinter looks dated — consider a lightweight web UI             |
| Config Storage       | JSON files                         | ✅ Good — simple, no database needed                               |
| Testing              | pytest                             | ✅ Good                                                            |

### 4.2 Recommended Changes

#### MCP SDK (High Priority)

Replace manual JSON-RPC handling with the official `mcp` Python SDK:

```python
# Current: manual dispatch in server.py (~200 lines)
# Proposed: 30 lines with mcp SDK
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities

server = Server("odoo-agent")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [...]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    return [...]
```

**Trade-off**: Adds a dependency, but eliminates ~200 lines of hand-rolled JSON-RPC and ensures spec compliance (Content-Length framing, proper error codes, etc.).

#### Vector Database → Schema Index (Simplify)

The current RAG pipeline (Chroma/PGVector) is overengineered for what it does: retrieving field metadata for prompt construction. With NO internal LLM, we don't need RAG at all — we just need a simple schema lookup:

```python
# Current: Chroma vector store → embed → query → retrieve
# Proposed: Direct dict lookup
schema = schema_store.get("shipment")
fields = schema.create_fields  # instant, no embedding needed
```

#### Desktop App Tkinter → Web UI

The current wizard uses tkinter, which:

- Requires Python/tkinter runtime
- Looks dated on macOS
- Is a separate codebase from the web UI

**Proposal**: Replace with a lightweight Flask-based setup page (already have Flask) served on localhost. The webapp already exists — just make it the default.

---

## 5. Refactoring Plan — Layer by Layer

### 5.1 New Directory Structure

```
odoo_agent_v2/
├── pyproject.toml
├── README.md
├── CLAUDE.md                      # Project instructions for Claude/Copilot
├── .github/
│   └── agents/                    # GitHub Copilot agent configs (.agent.md format)
│       ├── coder-tester.agent.md  # Write code + tests (TDD mandatory)
│       ├── maintainer.agent.md    # Architecture review, refactoring
│       ├── qa.agent.md            # Adversarial testing, edge cases
│       ├── cs.agent.md            # Customer Service Orchestrator
│       ├── salesman.agent.md      # Sales domain expert
│       ├── purchaser.agent.md     # Procurement domain expert
│       ├── logistics.agent.md     # Logistics & freight expert
│       └── accountant.agent.md    # Accounting & finance expert
├── docs/
│   ├── ARCHITECTURE.md
│   ├── MCP_SETUP.md
│   ├── CONTRIBUTING.md
│   └── agents/                    # Agent-specific documentation
│       ├── cs.md
│       ├── salesman.md
│       ├── purchaser.md
│       ├── logistics.md
│       └── accountant.md
├── config/
│   ├── config.template.json
│   ├── agents.json
│   └── schemas/                   # One JSON file per model (NOT a monolith)
│       ├── stock_picking.json
│       ├── sale_order.json
│       ├── purchase_order.json
│       ├── account_move.json
│       ├── shipment.json
│       └── ...
├── src/
│   ├── mcp_server/                # MCP protocol layer (thin)
│   │   ├── __init__.py
│   │   ├── server.py              # MCP SDK-based server (~80 lines)
│   │   ├── tools.py               # Tool definitions + handlers (~200 lines)
│   │   └── transport.py           # stdio/HTTP transport helpers
│   │
│   ├── odoo_service/              # Business logic layer (no AI)
│   │   ├── __init__.py
│   │   ├── router.py              # Keyword-based agent/model routing (~150 lines)
│   │   ├── odoo_client.py         # XML-RPC wrapper (~100 lines)
│   │   ├── schema_store.py        # Schema cache + lookup (~150 lines)
│   │   ├── session_store.py       # Session state management (~100 lines)
│   │   ├── schema_discovery.py    # Model introspection (~400 lines)
│   │   └── schema_enrichment.py   # AI-powered alias/keyword generation (~150 lines)
│   │
│   ├── operations/                # CRUD operations (stateless)
│   │   ├── __init__.py
│   │   ├── create.py              # Record creation + preview
│   │   ├── search.py              # Record search
│   │   ├── update.py              # Record update
│   │   ├── delete.py              # Record deletion
│   │   └── analytics.py           # Read-group aggregation
│   │
│   └── shared/                    # Shared types and utilities
│       ├── __init__.py
│       ├── types.py               # Dataclasses: ModelSchema, AgentConfig, SessionState
│       ├── config.py              # Configuration loader
│       └── date_utils.py          # Date helpers
│
├── installer/                     # Setup wizard (web-based, not tkinter)
│   ├── __init__.py
│   ├── wizard.py                  # Flask-based setup UI
│   └── templates/
│
├── tests/
│   ├── test_mcp_server.py
│   ├── test_router.py
│   ├── test_schema_store.py
│   ├── test_session_store.py
│   ├── test_odoo_client.py        # Mock-based
│   ├── test_operations.py
│   └── test_wizard.py
│
├── app_main.py                    # PyInstaller entry point
├── webapp.py                      # Dev web UI
└── build/
    └── OdooAIAgent.spec
```

### 5.2 Layer 1: MCP Server Layer (`src/mcp_server/`)

**Goal**: Thin JSON-RPC bridge. No business logic. ~300 lines total.

```python
# server.py — ~80 lines
from mcp.server import Server
from .tools import TOOLS, handle_tool_call

server = Server("odoo-agent")

@server.list_tools()
async def list_tools():
    return TOOLS

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    return await handle_tool_call(name, arguments)
```

```python
# tools.py — ~200 lines
# Only 3 tools needed:

TOOLS = [
    Tool(name="chat_odoo", description="Send a message to Odoo. ALWAYS use this for user messages.",
         inputSchema={"type": "object", "properties": {
             "message": {"type": "string", "description": "User's message verbatim"},
             "session_id": {"type": "string", "description": "Conversation session ID"},
         }, "required": ["message"]}),
    Tool(name="list_models", description="List available Odoo models and their fields."),
    Tool(name="list_agents", description="List available agent personas."),
]

async def handle_tool_call(name: str, args: dict):
    if name == "chat_odoo":
        return await chat_odoo_handler(**args)
    elif name == "list_models":
        return await list_models_handler()
    elif name == "list_agents":
        return await list_agents_handler()
```

**What's removed:**

- ❌ `search_odoo` — merged into `chat_odoo` (Claude can search via conversation)
- ❌ `analytics_odoo` — merged into `chat_odoo`
- ❌ `preview_odoo` / `create_odoo` / `delete_odoo` — already removed
- ❌ All LLM calls from within tools — Claude is the LLM

### 5.3 Layer 2: Odoo Service Layer (`src/odoo_service/`)

#### Router (`router.py`)

```python
def route_message(message: str, agents: dict) -> RouteResult:
    """Keyword-based routing. No LLM needed."""
    text = message.lower()
    scored = []
    for agent in agents.values():
        score = sum(len(kw) for kw in agent.keywords if kw.lower() in text)
        if score > 0:
            scored.append(RouteResult(agent.key, agent.default_model, score))
    return max(scored, key=lambda r: r.score) if scored else RouteResult(None, None, 0)
```

#### Schema Store (`schema_store.py`)

```python
class SchemaStore:
    """Loads model schemas from config/schemas/*.json. Caches in memory."""

    def __init__(self, schema_dir: str):
        self._schemas: dict[str, ModelSchema] = {}
        self._load_all(schema_dir)

    def get(self, model_key: str) -> ModelSchema: ...
    def list_all(self) -> list[ModelSchema]: ...
    def search(self, keyword: str) -> list[ModelSchema]: ...
```

#### Session Store (`session_store.py`)

```python
class SessionStore:
    """Simple dict-based session state. Keyed by session_id."""

    def get_state(self, session_id: str) -> SessionState: ...
    def set_state(self, session_id: str, state: SessionState): ...
    def get_last_agent(self, session_id: str) -> str: ...
    def set_last_agent(self, session_id: str, agent_key: str): ...
```

#### Schema Discovery (`schema_discovery.py`)

Completely rewritten from 1361 lines to ~500 lines using a deterministic-first, RAG-augmented approach:

```
┌──────────────────────────────────────────────────────────────────┐
│  SCHEMA DISCOVERY — Token-Efficient Architecture                 │
│                                                                  │
│  Phase 1: Deterministic Extraction (Zero AI tokens)              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ir.model.fields  → required, computed, related, selection   │ │
│  │ ir.ui.view       → field usage frequency per view type      │ │
│  │ ir.model.access  → CRUD permissions per group               │ │
│  │ fields_get()     → type, string, readonly, store, relation  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │                                       │
│                          ▼                                       │
│  Phase 2: View Frequency Analysis (Zero AI tokens)              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Parse form/tree/kanban/search views from ir.ui.view         │ │
│  │ Count field occurrences across all views                    │ │
│  │ Add usage_frequency: int to each FieldInfo                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │                                       │
│                          ▼                                       │
│  Phase 3: Embedding + Vector Index (Cheap, one-time)           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Per-model JSON → EMBEDDING MODEL → vector DB (pgvector)    │ │
│  │ Store: { model_key, json_schema, embedding, summary }      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │                                       │
│                          ▼                                       │
│  Phase 4: One-Time AI Summarization (Cached, per custom model)  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Standard models (res.partner, sale.order…) → skip (LLM     │ │
│  │ already knows them from Odoo training data)                │ │
│  │ Custom models (x_*, ops_logistics.*) → one-time 2-sentence │ │
│  │ summary via Anthropic Claude. Cached to disk forever.      │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

```python
# schema_discovery.py — ~500 lines

@dataclass
class FieldInfo:
    name: str
    field_type: str
    string: str
    required: bool
    readonly: bool
    store: bool
    computed: bool              # ← from ir.model.fields (zero tokens!)
    related: str = ""
    relation: str = ""
    selection: list = field(default_factory=list)
    depends: list = field(default_factory=list)
    usage_frequency: int = 0    # ← from ir.ui.view analysis (zero tokens!)

@dataclass
class ModelSchema:
    key: str
    label: str
    odoo_model: str
    summary: str = ""           # ← one-time AI summary (cached, only for custom models)
    all_fields: dict[str, FieldInfo]
    create_fields: list[str]
    search_fields: list[str]
    required_fields: list[str]
    field_aliases: dict[str, str]   # ← one-time AI enrichment (cached)
    match_keywords: list[str]       # ← one-time AI enrichment (cached)
    sub_models: list[SubModelSchema]
    usage_frequency_total: int = 0  # sum of all field frequencies

class SchemaDiscovery:
    def __init__(self, odoo: OdooClient, embedding_model: str = "BAAI/bge-small-en-v1.5"):
        self.odoo = odoo
        self.embedder = Embedder(embedding_model)  # lightweight local model

    # ── Phase 1: Deterministic extraction (ZERO AI TOKENS) ──────────

    def discover(self) -> dict[str, ModelSchema]:
        """Extract all metadata from Odoo ORM — no AI involved."""
        modules = self._list_installed_modules()
        models = self._filter_user_facing_models(modules)

        schemas = {}
        for model_name, label in models:
            raw_fields = self.odoo.fields_get(model_name)
            code_meta = self._query_ir_model_fields(model_name)  # computed/required/depends
            view_freqs = self._analyze_views(model_name)          # usage frequency

            fields = {}
            for fname, meta in raw_fields.items():
                fields[fname] = FieldInfo(
                    name=fname,
                    field_type=meta.get("type", ""),
                    string=meta.get("string", fname),
                    required=code_meta.get(fname, {}).get("required", False),
                    readonly=meta.get("readonly", False),
                    store=code_meta.get(fname, {}).get("store", True),
                    computed=bool(code_meta.get(fname, {}).get("compute")),
                    related=code_meta.get(fname, {}).get("related", ""),
                    relation=meta.get("relation", ""),
                    selection=meta.get("selection", []),
                    depends=code_meta.get(fname, {}).get("depends", []),
                    usage_frequency=view_freqs.get(fname, 0),
                )

            create_f, search_f, required_f = self._classify_fields(fields)
            schemas[model_name] = ModelSchema(
                key=model_name.replace(".", "_"),
                label=label,
                odoo_model=model_name,
                all_fields=fields,
                create_fields=create_f,
                search_fields=search_f,
                required_fields=required_f,
                sub_models=self._discover_sub_models(model_name, fields),
                usage_frequency_total=sum(f.usage_frequency for f in fields.values()),
            )

        return schemas

    def _query_ir_model_fields(self, model_name: str) -> dict:
        """Fetch computed/required/depends/store from ir.model.fields.

        This is deterministic metadata that Odoo's ORM already knows.
        We never ask AI to figure out which fields are computed or required.
        """
        model_id = self.odoo.search("ir.model", [("model", "=", model_name)], limit=1)
        if not model_id:
            return {}
        raw = self.odoo.search_read(
            "ir.model.fields",
            [("model_id", "=", model_id[0])],
            fields=["name", "compute", "related", "depends", "store", "required"],
        )
        return {
            r["name"]: {
                "compute": r.get("compute", ""),
                "related": r.get("related", ""),
                "depends": r.get("depends", []),
                "store": r.get("store", True),
                "required": r.get("required", False),
            }
            for r in (raw or [])
        }

    def _analyze_views(self, model_name: str) -> dict[str, int]:
        """Parse ir.ui.view XML to count field usage frequency.

        Counts how many times each field appears in form, tree, kanban,
        and search views.  Higher frequency = more contextually important.
        Costs ZERO AI tokens.
        """
        import re
        freq: dict[str, int] = {}

        views = self.odoo.search_read(
            "ir.ui.view",
            [("model", "=", model_name)],
            fields=["arch_db", "type"],
            limit=200,
        )

        FIELD_RE = re.compile(r'name="([a-z_][a-z0-9_]*)"')

        for view in (views or []):
            arch = view.get("arch_db", "") or ""
            # Weight: form views are most important, kanban less so
            weight = {"form": 3, "tree": 2, "kanban": 1, "search": 1}.get(
                view.get("type", ""), 1
            )
            for match in FIELD_RE.finditer(arch):
                fname = match.group(1)
                freq[fname] = freq.get(fname, 0) + weight

        return freq

    # ── Phase 2: Embedding + Vector Index (CHEAP, FAST) ────────────

    def index_to_vector_db(self, schemas: dict[str, ModelSchema]):
        """Embed each model schema and store in pgvector/ChromaDB.

        Each model's JSON schema (~2-10KB) is passed through a lightweight
        embedding model and stored in the vector database.  At query time,
        we retrieve only the top-K most relevant models — not all 200+.

        Embedding models (choose one):
          - Local: BAAI/bge-small-en-v1.5 (384 dims, <100MB, 5ms per embedding)
          - API:   OpenAI text-embedding-3-small (1536 dims, $0.02/1M tokens)
        """
        for key, schema in schemas.items():
            # Serialize the schema to a compact JSON string
            doc = json.dumps({
                "model": schema.odoo_model,
                "label": schema.label,
                "summary": schema.summary,
                "fields": {
                    fname: {
                        "type": fi.field_type,
                        "label": fi.string,
                        "required": fi.required,
                        "usage": fi.usage_frequency,
                    }
                    for fname, fi in schema.all_fields.items()
                    if fi.usage_frequency > 0 or fi.required
                },
            })

            # Compute embedding (the ONLY compute cost — trivial)
            embedding = self.embedder.embed(doc)

            # Store in vector DB
            self.vector_db.upsert(
                collection="odoo_schemas",
                id=key,
                embedding=embedding,
                metadata={"model_key": key, "odoo_model": schema.odoo_model},
                document=doc,
            )

    # ── Phase 3: One-time AI summarization (CACHED, custom models only) ──

    def enrich_custom_models(self, schemas: dict[str, ModelSchema]):
        """Generate a 2-sentence summary ONLY for custom models.

        Standard Odoo models (sale.order, res.partner, account.move, etc.)
        are already well-understood by LLMs from training data — we skip them.
        Custom models (x_*, ops_logistics.*, etc.) get a one-time summary that
        is cached to disk and never regenerated.
        """
        STANDARD_PREFIXES = (
            "res.", "sale.", "purchase.", "account.", "stock.", "crm.",
            "hr.", "project.", "mrp.", "product.", "mail.", "calendar.",
            "fleet.", "event.", "website.", "survey.", "base.",
        )

        for key, schema in schemas.items():
            if any(schema.odoo_model.startswith(p) for p in STANDARD_PREFIXES):
                continue  # LLM already knows this model

            # Check cache first
            cache_path = self.cache_dir / f"{key}_summary.txt"
            if cache_path.exists():
                schema.summary = cache_path.read_text().strip()
                continue

            # One-time AI call — only for custom models
            field_list = [
                f"  - {fname} ({fi.field_type}) [{fi.string}]"
                f"{' REQUIRED' if fi.required else ''}"
                for fname, fi in schema.all_fields.items()
                if fi.usage_frequency > 0 or fi.required
            ][:30]  # cap at 30 most-used fields

            prompt = (
                f"Model: {schema.odoo_model} ({schema.label})\n"
                f"Fields:\n" + "\n".join(field_list) + "\n\n"
                "Write a 2-sentence summary of what this model is used for."
            )

            summary = self.llm.ask(prompt, max_tokens=100)
            schema.summary = summary.strip()
            cache_path.write_text(schema.summary)

    def enrich_aliases(self, schemas: dict[str, ModelSchema]):
        """One-time AI enrichment for field aliases and match keywords.

        This is the same as the current _ai_enrich_model, but it only runs
        once and results are cached to disk.  Tries gh copilot first, falls
        back to Anthropic Claude.
        """
        for key, schema in schemas.items():
            enrichment = self._ai_enrich_single(schema)
            schema.field_aliases = enrichment.get("field_aliases", {})
            schema.match_keywords = enrichment.get("match_keywords", [])
```

**Key design decisions:**

| Approach                                                       | Token Cost                       | Speed         | Quality              |
| -------------------------------------------------------------- | -------------------------------- | ------------- | -------------------- |
| **Deterministic extraction** (ir.model.fields + view analysis) | 0 tokens                         | <1s per model | 100% accurate        |
| **Standard model skipping** (LLM already knows `sale.order`)   | 0 tokens                         | Instant       | High (training data) |
| **Vector DB filtering** (retrieve only relevant models)        | ~200 tokens                      | <10ms         | Excellent            |
| **One-time custom model summary**                              | ~100 tokens × custom models only | ~500ms        | Good                 |
| **One-time alias enrichment**                                  | ~500 tokens                      | ~3s per model | Excellent            |
| **Total for 200 models (90% standard)**                        | ~3,000 tokens total              | ~30s          | 95%+ quality         |

Compared to the current approach (AI enrichment for every model):

- **Token reduction: ~98%** (3,000 vs 150,000 tokens)
- **Time reduction: ~80%** (30s vs 2.5 min)

### 5.4 Layer 3: Operations (`src/operations/`)

Pure functions that take `OdooClient` + `ModelSchema` + parameters → return results:

```python
# create.py
def create_record(odoo: OdooClient, schema: ModelSchema, params: dict) -> CreateResult: ...

def preview_record(schema: ModelSchema, params: dict) -> PreviewResult: ...

# search.py
def search_records(odoo: OdooClient, schema: ModelSchema, filters: dict) -> SearchResult: ...

# update.py
def update_record(odoo: OdooClient, schema: ModelSchema, record_id: int, params: dict) -> UpdateResult: ...

# delete.py
def delete_record(odoo: OdooClient, schema: ModelSchema, target: dict) -> DeleteResult: ...

# analytics.py
def get_analytics(odoo: OdooClient, schema: ModelSchema, metric: str, periods: list) -> AnalyticsResult: ...
```

**What's removed:**

- ❌ `CreateEngine`, `SearchEngine`, `UpdateEngine`, `DeleteEngine` classes — replaced with pure functions
- ❌ `PluginRegistry` — domain logic becomes part of operations
- ❌ `MemoryManager` — conversation memory is the MCP client's responsibility
- ❌ `PromptBuilder` — no internal LLM, no prompts to build
- ❌ `ContextProvider` — replaced by schema-based field lookups
- ❌ `LearnedHints` — not needed without internal LLM

### 5.5 What's REMOVED Entirely

| File                                                                           | Reason                                          |
| ------------------------------------------------------------------------------ | ----------------------------------------------- |
| `conversation.py` (1383 lines)                                                 | No internal LLM → no conversation engine needed |
| `prompt_builder.py` (506 lines)                                                | No internal LLM → no prompts to build           |
| `context_provider.py` (157 lines)                                              | Replaced by schema-based lookups                |
| `create_engine.py`, `update_engine.py`, `delete_engine.py`, `search_engine.py` | Replaced by stateless operations module         |
| `plugins/` (entire directory)                                                  | Domain logic merged into operations             |
| `rag/` (entire directory)                                                      | No RAG needed without internal LLM              |
| `memory/` (entire directory)                                                   | Session store handles state, not vector memory  |
| `baseline/` (entire directory)                                                 | Schema discovery replaces baseline diff         |
| `synthesis.py`                                                                 | No response synthesis without internal LLM      |
| `learned_hints.py`                                                             | Not needed                                      |
| `relational_query.py`                                                          | Sub-models handled by operations                |
| `model_guide.py`                                                               | Not needed                                      |
| `bootstrap.py`                                                                 | Schema discovery handles this                   |
| `_gh_utils.py`                                                                 | Only needed for Copilot CLI in enrichment       |
| `tracing.py`, `date_utils.py`, `cache_store.py`                                | Merged into shared utils as needed              |
| `model_configs/model_configs.json` (30K lines)                                 | Split into `config/schemas/*.json`              |
| `crews_council.py` (195 lines)                                                 | Merged into router                              |
| `agent_council.py` (585 lines)                                                 | Simplified into router                          |
| `cs_orchestrator.py` (982 lines)                                               | Simplified into router                          |

**Net reduction: ~12,000 lines → ~2,000 lines (~83% reduction)**

---

## 6. AI Strategy — Single AI, No Internal Engine

### The Core Insight

When using MCP, the MCP client (Claude Desktop) already has a powerful LLM. Having our own internal LLM:

- **Wastes tokens** (two AIs processing the same message)
- **Creates confusion** (which AI is "in charge"?)
- **Costs more** (two API calls instead of one)
- **Adds latency** (two serial LLM calls)

### The New Model

```
User: "Create a shipment for ACME Corp"
    │
    ▼
Claude (MCP Client): Understands the intent, knows what data is needed
    │
    │ calls chat_odoo(message="Create a shipment for ACME Corp")
    ▼
MCP Server:
    1. Route to logistics agent based on keywords
    2. Look up "shipment" model schema
    3. Return schema + current state to Claude
    │
    ▼
Claude: "I see you want to create a shipment. The required fields are:
         partner_id (Customer), picking_type_id (Operation Type), ...
         Which customer is this for?"
    │
    ▼
User: "ACME Corp"
    │
    ▼
Claude: calls chat_odoo(message="ACME Corp", session_id="abc123")
    │
    ▼
MCP Server:
    1. Look up "ACME Corp" in res.partner via Odoo
    2. Return search results to Claude
    │
    ▼
Claude: "Found ACME Corp (ID: 42). Here's a preview:
         - Customer: ACME Corp
         - Operation: Delivery Order
         Should I create this?"
```

**Claude handles ALL conversational logic.** The MCP server just provides:

1. Model schemas (what fields exist, which are required)
2. Data lookups (search partners, products, etc.)
3. Record operations (create, search, update, delete)
4. Session state (remember what we're working on)

### Schema Enrichment (the ONLY place we use our own AI)

Schema discovery still benefits from AI for generating:

- Field aliases (e.g., "customer" → `partner_id`)
- Match keywords (e.g., "SO" → `sale_order`)
- Model descriptions

This is a **one-time offline process** (run during setup, cached to disk), not a runtime LLM call. We use Claude's API (via `anthropic` SDK) for this, NOT `gh copilot` CLI:

```python
def enrich_schema(schema: ModelSchema) -> ModelSchema:
    """One-time AI enrichment. Result cached to disk."""
    llm = LLM(provider="anthropic", model="claude-sonnet-4-20250514")
    prompt = f"Analyze this Odoo model: {schema.odoo_model}\nFields: {schema.fields}\n..."
    result = llm.ask_json(prompt)
    schema.aliases = result["field_aliases"]
    schema.keywords = result["match_keywords"]
    return schema
```

---

## 7. Documentation & GitHub/AI Agent Handling

### 7.1 Documentation Structure

```
docs/
├── ARCHITECTURE.md        # System design, data flow, key decisions
├── MCP_SETUP.md           # How to configure Claude Desktop
├── MODEL_SCHEMAS.md       # How schema discovery works
├── CONTRIBUTING.md        # Dev setup, testing, PR process
├── CHANGELOG.md           # Version history
└── agents/                # Agent-specific docs
    ├── orchestrator.md    # CS Orchestrator behavior
    ├── logistics.md       # Logistics agent: shipments, deliveries
    ├── salesman.md        # Sales agent: orders, quotations
    ├── accountant.md      # Accounting agent: invoices, payments
    ├── purchaser.md       # Purchase agent: POs, vendors
    └── hr.md              # HR agent: employees, departments
```

### 7.2 GitHub Copilot Agent Customization

The `.github/agents/` directory already contains agent definitions. For the rewrite, enhance them:

```markdown
# .github/agents/coder-tester.agent.md

---

name: Coder/Tester
description: Write code and tests together
model: claude-sonnet-4.6
tools: file_search, grep_search, read_file, replace_string_in_file, run_in_terminal

---

You are an expert software developer for the Odoo AI Agent project.
This project uses:

- Python 3.9+ with type hints
- MCP (Model Context Protocol) for Claude Desktop integration
- XML-RPC for Odoo communication
- pytest for testing

Key rules:

- NEVER call `gh copilot` CLI — use `anthropic` SDK directly
- Write tests BEFORE implementation (TDD)
- Use `src/odoo_service/` for business logic, `src/mcp_server/` for protocol
- Keep tools.py handlers thin — delegate to service layer
```

### 7.3 CLAUDE.md / Copilot Instructions

Add a `CLAUDE.md` at the repo root (Claude Desktop and Copilot both read this):

```markdown
# CLAUDE.md — Odoo AI Agent

## Project Overview

MCP server that connects Claude Desktop to Odoo ERP. Claude is the AI — the server
is a thin bridge that provides Odoo data access and CRUD operations.

## Architecture

- `src/mcp_server/` — MCP protocol layer (tools, server, transport)
- `src/odoo_service/` — business logic (router, schema store, Odoo client)
- `src/operations/` — stateless CRUD functions
- `config/schemas/` — cached model schemas (one JSON per model)
- `installer/` — web-based setup wizard

## Key Rules

1. No LLM calls in runtime code — Claude IS the LLM
2. No internal conversation state — use session_id for statelessness
3. All Odoo calls go through odoo_client.py
4. Schema enrichment is a one-time setup step, not runtime
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Week 1)

- [ ] Create new `odoo_agent_v2/` directory with clean structure
- [ ] Set up `pyproject.toml` with minimal dependencies
- [ ] Implement `src/shared/types.py` — all dataclasses
- [ ] Implement `src/shared/config.py` — config loader
- [ ] Implement `src/odoo_service/odoo_client.py` — XML-RPC wrapper
- [ ] Write tests for all of the above

### Phase 2: Schema & Discovery (Week 1-2)

- [ ] Implement `src/odoo_service/schema_store.py` — load/save/lookup
- [ ] Implement `src/odoo_service/schema_discovery.py` — introspect Odoo
- [ ] Implement `src/odoo_service/schema_enrichment.py` — AI aliases/keywords
- [ ] Split `model_configs.json` into `config/schemas/*.json`
- [ ] Write tests

### Phase 3: Operations (Week 2)

- [ ] Implement `src/operations/search.py`
- [ ] Implement `src/operations/create.py`
- [ ] Implement `src/operations/update.py`
- [ ] Implement `src/operations/delete.py`
- [ ] Implement `src/operations/analytics.py`
- [ ] Write tests

### Phase 4: MCP Server (Week 2-3)

- [ ] Implement `src/mcp_server/server.py` (with `mcp` SDK)
- [ ] Implement `src/mcp_server/tools.py` (3 tools: chat_odoo, list_models, list_agents)
- [ ] Implement `src/mcp_server/transport.py` (stdio + HTTP)
- [ ] Implement `src/odoo_service/router.py` — keyword routing
- [ ] Implement `src/odoo_service/session_store.py` — session state
- [ ] Write tests

### Phase 5: Routing & Agents (Week 3)

- [ ] Implement `src/odoo_service/router.py` — complete agent routing
- [ ] Port `agents.json` to new format
- [ ] Implement session memory (last agent/model per session)
- [ ] Write integration tests

### Phase 6: Installer & Packaging (Week 3-4)

- [ ] Implement `installer/wizard.py` — Flask-based setup UI
- [ ] Update `OdooAIAgent.spec` for PyInstaller
- [ ] Test on macOS .app bundle
- [ ] Update Claude Desktop config auto-registration

### Phase 7: Polish (Week 4)

- [ ] Documentation (`docs/`)
- [ ] GitHub Copilot agent configs (`.github/agents/`)
- [ ] `CLAUDE.md` / `AGENTS.md`
- [ ] Final integration testing with real Odoo + Claude Desktop
- [ ] Performance testing (schema discovery speed, tool call latency)
