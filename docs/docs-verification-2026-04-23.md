# Anthropic docs verification — 2026-04-23

Verified against `https://platform.claude.com/docs/en/...` (the new home for `docs.claude.com`, which 302-redirects there).

This file captures **divergences between the Tech Spec v1.0 and the current Anthropic docs**. Trust the docs over the spec where they conflict — update the spec on the next revision.

## Confirmed ✅

| Item | Spec value | Docs value | Status |
|------|------------|------------|--------|
| Opus 4.7 model ID | `claude-opus-4-7` | `claude-opus-4-7` | ✅ |
| Haiku 4.5 model ID | `claude-haiku-4-5-20251001` | `claude-haiku-4-5-20251001` | ✅ |
| Memory tool type | `memory_20250818` | `memory_20250818` | ✅ |
| Context management beta header | `context-management-2025-06-27` | `context-management-2025-06-27` | ✅ |

## Divergences — the Tech Spec is wrong, use these values instead ❌

### 1. Opus 4.7 thinking API shape — **breaking change**

**Spec (wrong):**
```python
thinking={"type": "enabled", "budget_tokens": 8000, "display": "summarized"}
```

**Docs (correct):** Opus 4.7 **only** supports adaptive thinking. `type: "enabled"` is rejected with HTTP 400.
```python
thinking={"type": "adaptive", "display": "summarized"}
output_config={"effort": "xhigh"}  # "low" | "medium" | "high" (default) | "xhigh" | "max"
```

- On Opus 4.7 `display` defaults to `"omitted"` (silent change from 4.6), so the demo trace needs an **explicit** `display: "summarized"`.
- Adaptive thinking auto-enables interleaved thinking — no beta header needed.
- `budget_tokens` doesn't exist for adaptive; use `max_tokens` as the hard output cap and `effort` as soft guidance.

### 2. `extended-thinking-2025-xx-xx` beta header — **does not exist**

The Tech Spec’s `ANTHROPIC_BETA_HEADERS` string contains `extended-thinking-2025-xx-xx` as a placeholder. There has never been an extended-thinking beta header on Claude 4 models — it's a core API feature. **Remove it entirely from `.env` and `BETA_HEADERS`.**

### 3. Memory tool does **not** require a beta header

Spec implies `memory-20250818` belongs in the `anthropic-beta` header. Docs show plain `client.messages.create(...)` with `tools=[{"type":"memory_20250818","name":"memory"}]` — no `anthropic-beta` string. The "20250818" is the **tool type identifier**, not a header value.

### 4. Memory tool is client-side — no `root` field

Spec includes `"root": "/memories/{user_id}"` in the tool definition. The docs tool schema is just `{"type":"memory_20250818","name":"memory"}`. Root scoping is entirely a **client-side** concern: our handler enforces `/memories/{user_id}/` via path-canonicalization before executing `view`/`create`/`str_replace`/`insert`/`delete`/`rename`.

### 5. Context editing lives on the **beta** client

Context editing uses `client.beta.messages.create(...)` with `betas=["context-management-2025-06-27"]` and a `context_management={"edits":[{"type":"clear_tool_uses_20250919"}, ...]}` param — not just a header on the vanilla client. For Day 1 we don't use context editing; we'll wire it up on the ReportAgent path when we cross ~500K token conversations.

## Locked for Day 1

```python
# app/llm/opus.py
MODEL_OPUS = "claude-opus-4-7"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

EFFORT_MAP = {
    "medium": "medium",
    "high":   "high",
    "xhigh":  "xhigh",
}

def opus_call(system, user, effort="high", tools=None, max_tokens=4096):
    return client.messages.create(
        model=MODEL_OPUS,
        max_tokens=max_tokens,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": EFFORT_MAP[effort]},
        system=system,
        tools=(tools or []) + [{"type": "memory_20250818", "name": "memory"}],
        messages=[{"role": "user", "content": user}],
        metadata={"agent": "opus", "effort": effort},
    )
```

No `anthropic-beta` header is needed for this baseline call. Add `betas=["context-management-2025-06-27"]` and switch to `client.beta.messages.create` **only** when enabling `clear_tool_uses_20250919` on the ReportAgent.

## Action items

- [ ] Update Tech Spec §5.2 `opus_call()` to use adaptive thinking.
- [ ] Update Tech Spec §4.2.1 DDISubAgent invocation to drop `budget_tokens` and the fake `extended-thinking-2025-xx-xx` header.
- [ ] Update `.env.example` `ANTHROPIC_BETA_HEADERS` to only list headers actually needed (see above).
