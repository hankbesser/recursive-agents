# Memory Architecture in Recursive Agents MCP

This document explains the complete memory system, how it flows through middleware, and how different layers interact to create an intelligent reasoning system.

## Overview: Three Memory Layers

The system operates with three distinct memory layers that work together:

1. **Persistent Memory** (BaseCompanion)
   - `history`: Conversation messages (Human/AI pairs)
   - `run_log`: Iteration slots with phase arrays

2. **Request Memory** (ctx.state)
   - `phase_tracking`: Current position and metrics
   - `suggestions`: Next action guidance
   - `convergence_signals`: Quality indicators

3. **Tool Memory** (Phase-specific views)
   - Draft: Sees full history
   - Critique: Sees sliding window of drafts/revisions
   - Revise: Sees current draft and critique

## The run_log Structure: Heart of the System

Each slot in `run_log` represents a complete reasoning cycle:

```python
{
    "query": "What causes X?",              # The question being analyzed
    "draft": "Initial analysis...",         # Single baseline draft (sacred)
    "critique": [                           # Array of critiques
        "First critique identifying gaps",
        "Second critique on improvements",
        "Third critique finding minor issues"
    ],
    "revision": [                           # Array of revisions (aligned with critiques)
        "First revision addressing gaps",
        "Second revision with improvements"
        # Note: len(revision) <= len(critique) always!
    ],
    "variant": "gpt-4o-mini",              # Model/execution variant
    "sampling": {...}                       # Sampling configuration
}
```

### The Array Synchronization Pattern

The genius of this design is that array lengths tell us EXACTLY where we are:

```python
# State 1: Fresh start
critique = []
revision = []
→ Next: draft

# State 2: Draft exists
critique = []
revision = []
→ Next: critique

# State 3: Critique without revision
critique = ["C1"]
revision = []
→ Next: MUST revise

# State 4: Equal arrays
critique = ["C1", "C2"]
revision = ["R1", "R2"]
→ Next: Can critique again OR finalize

# State 5: Imbalanced (needs revision)
critique = ["C1", "C2", "C3"]
revision = ["R1", "R2"]
→ Next: MUST revise to balance
```

## History Management: Bounded Context

The `history` list contains LangChain messages but is kept bounded:

```python
def trim_history(hist, max_pairs: int = 3):
    """Keep only the newest 3 (Human, AI) pairs"""
    excess = len(hist) - max_pairs * 2
    if excess > 0:
        del hist[:excess]  # Remove oldest
```

This ensures:
- Recent context is preserved
- Token costs stay manageable
- Conversation doesn't drift too far

### History Updates

Each phase updates history differently:
- **Draft**: Adds new Human/AI pair
- **Critique**: No history update (internal analysis)
- **Revise**: Replaces last AI message with revision

## Phase-Specific Memory Views

### Draft Phase Memory

Sees everything:
- Full conversation history
- Previous run_log slots
- Can detect if query is new or continuation

```python
# Check if new query
if is_new_query(comp, params.query):
    # Create new slot
else:
    # Continue in current slot (with validation)
```

### Critique Phase Memory: The Sliding Window

The most sophisticated memory pattern:

```python
def last_n_drafts(companion, query: str, n: int = 3) -> str:
    # ALWAYS include baseline draft first
    drafts.append(f"[ORIGINAL BASELINE]\n{current_slot['draft']}")
    
    # Add recent revisions (max 2)
    revisions = current_slot.get("revision", [])
    if revisions:
        recent_revisions = revisions[-(n-1):]  # Last 2
        for i, rev in enumerate(recent_revisions):
            drafts.append(f"[ITERATION {num}]\n{rev}")
```

This creates a "sliding window" where critique sees:
1. **Original baseline** (always, for reference)
2. **Last 2 revisions** (to track evolution)

This allows critique to understand the journey, not just the destination.

### Revise Phase Memory

Sees focused context:
- Current draft (or latest revision)
- Latest critique
- Original query

## Middleware Memory Bridge

### State Bridge Pattern

Middleware creates a bridge between persistent and ephemeral memory:

```
Session State (CompanionSessionManager)     Request State (ctx.state)
┌─────────────────────────┐                ┌─────────────────────────┐
│ companion.history       │ ←─────────────→ │ phase_tracking         │
│ companion.run_log       │     Bridge      │ suggestions            │
│ companion.preferences   │                 │ convergence_signals    │
└─────────────────────────┘                └─────────────────────────┘
        Persistent                                 Ephemeral
```

### How Middleware Reads Memory

```python
# PhaseIntelligenceMiddleware analyzes state
async def _analyze_iteration_state(self, context, ctx):
    # Get companion (persistent memory)
    comp = session_manager.get_companion(session_id, companion_type)
    current_slot = comp.run_log[-1]
    
    # Analyze arrays to determine position
    critiques = current_slot.get("critique", [])
    revisions = current_slot.get("revision", [])
    
    # Determine phase position from array lengths
    if len(critiques) == len(revisions):
        current_phase = "critique"  # Can critique again
        iteration_number = len(critiques)
    elif len(critiques) > len(revisions):
        current_phase = "revise"    # Must revise
        iteration_number = len(revisions)
```

### What Goes in ctx.state

Request-scoped intelligence that enhances the persistent memory:

```python
ctx.state = {
    "phase_tracking": {
        "current_tool": "critique",
        "iteration_number": 2,
        "total_iterations": 5,
        "phase_sequence": [
            {"phase": "draft", "timestamp": "..."},
            {"phase": "critique", "timestamp": "..."},
            {"phase": "revise", "timestamp": "..."}
        ],
        "phase_timings": {
            "draft_0": 1.2,
            "critique_0": 0.8,
            "revise_0": 1.5
        }
    },
    "suggestions": {
        "next_action": "revise",
        "message": "Critique complete. Ready to implement improvements.",
        "confidence": "high",
        "iteration_context": {
            "current_iteration": 2,
            "total_time": 45.3
        }
    },
    "convergence_signals": [
        {"type": "iteration_count", "strength": "medium"},
        {"type": "duration", "strength": "low"}
    ]
}
```

## Memory Validation Rules

### PhaseValidationMiddleware enforces:

1. **Draft Constraints**:
   - Cannot create new draft if revisions exist for same query
   - Preserves iteration chain integrity
   - Forces query modification for fresh start

2. **Critique Requirements**:
   - Must have draft in current slot
   - Validates before allowing critique

3. **Revise Requirements**:
   - Must have both draft AND critique
   - Arrays must be unbalanced (more critiques than revisions)

## Memory Flow Through Request Lifecycle

```
1. Request Arrives
   ↓
2. PhaseValidation checks memory state
   - Reads run_log arrays
   - Validates phase transition
   ↓
3. PhaseIntelligence analyzes memory
   - Calculates iteration position
   - Adds intelligence to ctx.state
   ↓
4. Tool executes with enriched context
   - Reads from ctx.state
   - Updates companion memory
   - Uses phase-specific views
   ↓
5. Response includes suggestions
   - Next action guidance
   - Convergence indicators
```

## Memory Consistency Guarantees

1. **Baseline Preservation**: Original draft never modified
2. **Array Alignment**: `len(revision) <= len(critique)` always
3. **History Bounding**: Maximum 3 conversation pairs
4. **State Isolation**: Child contexts can't corrupt parent state
5. **Session Persistence**: Memory survives across requests

## Advanced Memory Patterns

### Cross-Session Learning (Future)

The PhaseIntelligenceMiddleware tracks global metrics:

```python
self.global_metrics = {
    "avg_iterations_by_type": {
        "marketing": 2.3,
        "bug_triage": 3.1,
        "strategy": 2.7
    },
    "convergence_patterns": [
        {"query_type": "analysis", "avg_iterations": 2.5}
    ]
}
```

This enables:
- Predicting iteration count
- Suggesting optimal temperature
- Early convergence detection

### Memory Resources (Future Enhancement)

Exposing memory through MCP resources:

```
resource://sessions/{id}/latest_critique
resource://sessions/{id}/baseline_draft
resource://sessions/{id}/iteration_timeline
resource://sessions/{id}/convergence_analysis
```

## Key Insights

1. **Memory is Multi-Layered**: Not just storage, but structured intelligence
2. **Arrays Tell Stories**: The critique/revision arrays encode the full journey
3. **Windows Preserve Context**: Sliding windows show evolution without overwhelming
4. **Middleware Adds Intelligence**: Makes implicit patterns explicit and actionable
5. **Validation Preserves Integrity**: Rules ensure memory stays consistent

The beauty of this system is that complex memory patterns emerge from simple array structures, and middleware makes that complexity intelligently accessible without changing the underlying elegance.