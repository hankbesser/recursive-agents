# MCP Development Notes

## What Happens with the Nesting in get_companion()

When the lock was added, the companion creation code became nested inside `if companion_type not in companions:`.

**What this means:**

1. **Companion exists**: The entire creation block is skipped. We go straight to `return companions[companion_type]`

2. **Companion doesn't exist**: We enter the if block, create the companion with the provided config, store it, then return it.

**Side effect discovered**: If you call get_companion twice with different configs for the same companion_type, the second config is completely ignored. The companion keeps its original config from first creation.

This was true before the lock too - the nesting just made it more obvious.

## Similarity Score Calculation

**Implementation**: Similarity scores are calculated in the revise tool when:
1. Execution mode is SERVER (no API calls in client mode)
2. There are 2+ revisions to compare
3. User hasn't explicitly disabled it via `calculate_similarity=False`

**User Control**: The revise tool accepts `calculate_similarity` parameter:
- `True`: Always calculate (if server mode and 2+ revisions)
- `False`: Never calculate
- `None` (default): Calculate automatically in server mode with 2+ revisions

**Rationale**: Users control whether they want to pay for embedding API calls. Default is sensible (auto in server mode) but can be overridden.

**Storage**: Similarity score is stored in `run_log[slot]["similarity_score"]` as a float between 0 and 1.

**Requirements**: Must use `chain_V2.py` which has:
- Global `GLOBAL_EMBEDDINGS` instance
- Public `calculate_similarity()` method on BaseCompanion

**Note**: To use this feature, update imports from `core.chains` to `core.chain_V2`

## Session Persistence with Redis

**Implementation**: Sessions and companions are now optionally persisted to Redis.

**Features**:
- Automatic save after companion modifications
- Automatic save after middleware state updates
- Load on first access if exists in Redis
- Falls back gracefully to memory-only if Redis unavailable
- 24-hour TTL on Redis keys

**Configuration**:
```python
# With Redis
session_manager = CompanionSessionManager(redis_url="redis://localhost:6379")

# Without Redis (memory-only, backward compatible)
session_manager = CompanionSessionManager()
```

**What gets persisted**:
- Companion state (history, run_log, config)
- Session metadata (created_at, last_accessed)
- Middleware state (cross-request data)
- Similarity scores (when calculated)

**Serialization**: JSON for everything (secure, debuggable)
- LangChain messages converted to simple dicts
- Datetime objects converted to ISO strings
- Custom attributes preserved

## Simplified Phase Metrics Middleware

**Replaced**: PhaseIntelligenceMiddleware was overly complex with fake "intelligence"

**New PhaseMetricsMiddleware** tracks real metrics:
- Iteration counts per phase
- Average phase durations (exponential moving average)
- Similarity scores from run_log
- Actual convergence detection (similarity >= threshold)
- Failure tracking

**Stored in persistent middleware_state**:
```json
{
  "metrics": {
    "total_requests": 42,
    "phase_counts": {"draft": 10, "critique": 16, "revise": 16},
    "average_durations": {"draft": 2.3, "critique": 1.8, "revise": 2.5},
    "last_similarity_score": 0.982,
    "convergence_detected": true,
    "failures": []
  }
}
```

**No more**:
- String pattern matching for "intelligence"
- Hardcoded suggestions
- Fake convergence signals
- Ephemeral ctx.state that dies