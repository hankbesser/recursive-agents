# Recursive Agents MCP Middleware

This directory contains middleware that enhances the three-phase reasoning system.

## Middleware Stack

Middleware executes in order:

1. **PhaseValidationMiddleware** - Validates phase transitions
   - Ensures critique requires draft
   - Ensures revise requires critique
   - Blocks draft creation when revisions exist

2. **PhaseIntelligenceMiddleware** - Adds intelligence layer
   - Tracks iteration progress and timing
   - Suggests next actions
   - Detects convergence signals
   - Maintains cross-session metrics

## How Tools Use Middleware Intelligence

The middleware adds intelligence to `ctx.state` that tools can access:

```python
# In any tool (draft, critique, revise)
async def tool_critique(params: CritiqueDraftInput, ctx: Context):
    # Access suggestions from middleware
    suggestions = ctx.get_state("suggestions")
    if suggestions:
        next_action = suggestions.get("next_action")
        message = suggestions.get("message")
        # Tool can include this in response or logs
    
    # Access phase tracking
    phase_tracking = ctx.get_state("phase_tracking")
    if phase_tracking:
        iteration_num = phase_tracking.get("iteration_number")
        total_time = phase_tracking.get("total_duration")
        # Tool can adapt behavior based on iteration count
    
    # Access convergence signals
    convergence = ctx.get_state("convergence_signals")
    if convergence:
        # Tool might suggest stopping if convergence detected
```

## Understanding the Memory Model

The middleware bridges two memory layers:

### Session Memory (Persistent)
- `companion.history`: Conversation messages
- `companion.run_log`: Array of iteration slots
  ```python
  {
      "query": "...",
      "draft": "...",
      "critique": ["critique1", "critique2"],
      "revision": ["revision1", "revision2"]
  }
  ```

### Request Memory (ctx.state)
- `phase_tracking`: Current phase position and history
- `suggestions`: Next action recommendations
- `convergence_signals`: Iteration quality indicators

## Phase Position Logic

The middleware determines phase position by analyzing arrays:

```python
critiques = ["c1", "c2"]
revisions = ["r1", "r2"]
# Equal lengths = ready for new critique

critiques = ["c1", "c2", "c3"]
revisions = ["r1", "r2"]
# More critiques = need to revise

critiques = ["c1"]
revisions = []
# Critique without revision = must revise next
```

## Adding New Middleware

To add new middleware:

1. Create a new file in this directory
2. Extend the `Middleware` base class
3. Override relevant hooks (`on_call_tool`, etc.)
4. Register in `NEWST_server_v2.py` in desired order

## Future Enhancements

- **Learning Middleware**: Track patterns across users
- **Quality Scoring**: Rate iteration improvements
- **Auto-Stop**: Halt when quality plateaus
- **Cost Tracking**: Monitor token usage per phase