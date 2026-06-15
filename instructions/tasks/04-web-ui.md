# Task: Web UI — Flask Chat Interface

**Created:** 2026-06-15  
**Status:** 🔴 Not started  
**Priority:** MEDIUM — makes the agent usable outside Claude Desktop  
**Depends on:** Phase 3 (operations), Phase 4 (MCP transport)

---

## Problem

The only way to interact with the Odoo AI agent is through Claude Desktop's MCP client. We need a standalone web UI for:

- Development and testing
- Users who don't use Claude Desktop
- Schema browsing and exploration

## Files to Create/Modify

| File                   | Purpose                                                       |
| ---------------------- | ------------------------------------------------------------- |
| `webapp.py`            | Flask server (~150 lines): serve UI, proxy MCP calls          |
| `templates/index.html` | Chat interface: message input, conversation history           |
| `static/app.js`        | Client-side: fetch /api/chat, render messages, manage session |
| `static/styles.css`    | Minimal styling                                               |

## Specifications

### Backend (`webapp.py`)

```python
# Routes:
GET  /              → serve index.html
POST /api/chat      → {message, session_id} → {response, agent, model}
GET  /api/models    → list available schemas
GET  /api/agents    → list available agents
GET  /api/health    → {"status": "ok"}
```

The `/api/chat` endpoint:

1. Routes message via `router.route_message()`
2. Looks up schema via `schema_store.get()`
3. Executes operation if intent is clear (search/create/update)
4. Returns structured response

### Frontend (`static/app.js`)

- Single-page chat UI
- Message bubbles (user / agent)
- Session persistence via localStorage
- Schema viewer panel (collapsible sidebar)
- "New conversation" button

## Test Categories

- [ ] Handler tests (test Flask routes directly, not HTTP)
- [ ] Chat endpoint: valid message → structured response
- [ ] Chat endpoint: empty message → error
- [ ] Models/agents endpoints: return JSON
- [ ] Health check: returns 200

## Acceptance Criteria

- [ ] `python webapp.py` starts a working chat UI at localhost:5000
- [ ] Messages route to correct agent and return useful responses
- [ ] Session state persists across messages
- [ ] Schema viewer shows available models
