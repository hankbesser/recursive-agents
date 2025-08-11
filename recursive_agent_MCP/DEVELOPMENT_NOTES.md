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
3. `enable_similarity` is True (or None, which defaults to True in server mode)

**Configuration**: 
- Set via `SamplingConfig.enable_similarity` 
- Stored on companion instance at creation
- Defaults: True for server mode, False for client mode

**Storage**: Similarity score is stored in `run_log[slot]["similarity_score"]` as a float between 0 and 1.

**Requirements**: Must use `chain_V2.py` which has:
- Global `GLOBAL_EMBEDDINGS` instance
- Public `calculate_similarity()` method on BaseCompanion