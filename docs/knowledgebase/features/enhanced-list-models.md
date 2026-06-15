# Feature: Enhanced `list_models` — Semantic Model Discovery

**Implemented:** 2026-06-15
**Files:** `src/mcp_server/tools.py` (score_model_relevance, \_format_model_entry, list_models_handler)
**Tests:** 8 tests in `tests/test_mcp_tools_v2.py`

## What It Does

`list_models` now supports an optional `message` parameter. When provided, models are scored by relevance to the message and sorted with the best matches first.

This lets Claude semantically discover models when the keyword router fails — without needing a vector database.

### Scoring Algorithm (Zero Tokens, Pure Python)

1. **Keyword substring matches** — `len(keyword)` per match
2. **Label exact match** — +5 if model label appears in message
3. **Model name word overlap** — +3 per matching word
4. **Summary word overlap** — +1 per matching word

### Usage

```
# Before (routing only):
User: "Track containers on vessels"
  → router: no keyword match → dead end
  → Claude: "I don't understand"

# After (semantic + routing):
User: "Track containers on vessels"
  → Claude calls: list_models(message="Track containers on vessels")
  → Server returns top 10 by relevance:
    1. x_container.tracking [relevance: 12] — "Tracks shipping containers..."
    2. stock.picking [relevance: 8] — "Stock transfer document..."
    3. ...
  → Claude: "x_container.tracking looks right. Let me check its fields."
```

### Design Decisions

- **Backward compatible** — no message = all models alphabetically
- **Zero tokens** — pure Python code, no API calls
- **Caps at top_n=10** — Claude has limited context window
- Response includes keywords, field count, required fields, summary per model
