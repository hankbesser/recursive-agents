# Complete State and Session Flow Analysis: From Protocol to Persistence

## Table of Contents
1. [The Complete State Hierarchy](#the-complete-state-hierarchy)
2. [Layer-by-Layer Breakdown](#layer-by-layer-breakdown)
3. [Memory Flow Through Draft → Critique → Revise](#memory-flow-through-draft--critique--revise)
4. [What Gets Stored Where](#what-gets-stored-where)
5. [Context Flow Through Your Application](#context-flow-through-your-application)
6. [Persistence Strategy](#persistence-strategy)

## The Complete State Hierarchy

Here's every level of state/session management from the protocol up through your application:

```
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 0: MCP Protocol (Stateless)                               │
│ - Pure request/response                                          │
│ - No session concept                                             │
│ - JSON-RPC messages                                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 1: Python MCP SDK                                          │
│ - ServerSession (connection lifetime)                            │
│   └── Lives: Client connect → disconnect                         │
│ - RequestContext (request lifetime)                              │
│   └── Lives: Request arrival → response sent                     │
│ - Uses contextvars for request isolation                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 2: FastMCP 2.11.1                                          │
│ - Context._state dict (request lifetime)                         │
│   └── Lives: Request start → request end                         │
│ - ctx.session_id (connection lifetime via ServerSession)         │
│   └── Stored as ServerSession._fastmcp_id                        │
│ - Middleware can use ctx.set_state/get_state                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 3: Your CompanionSessionManager (In-Memory)                │
│ - sessions[session_id] (memory lifetime)                         │
│   └── Lives: Creation → TTL expiry or server restart            │
│ - Contains BaseCompanion instances                               │
│   └── history: List[HumanMessage|AIMessage]                      │
│   └── run_log: List[Dict] with query/draft/critique/revision    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 4: V2 Hybrid Storage (Proposed)                            │
│ - In-memory cache (same as Level 3)                              │
│ - Redis persistence (survives restart)                           │
│   └── Serialized companion state                                 │
│ - Background sync between memory and Redis                       │
└─────────────────────────────────────────────────────────────────┘
```

## Layer-by-Layer Breakdown

### Level 0: MCP Protocol
```json
// Pure JSON-RPC - no state
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "draft",
    "arguments": {"query": "Analyze revenue"}
  },
  "id": 1
}
```
**Lifetime**: Single request/response
**Storage**: None - purely transient

### Level 1: Python MCP SDK

```python
# ServerSession - lives for entire connection
class ServerSession:
    _client_params: InitializeRequestParams  # Client capabilities
    _in_flight: dict[RequestId, RequestResponder]  # Active requests
    # NO USER DATA STORAGE

# RequestContext - lives for one request
@dataclass
class RequestContext:
    request_id: RequestId        # "req_123"
    session: ServerSession       # Reference to long-lived session
    meta: RequestParams.Meta     # Progress tokens, etc.
```

**What survives across requests**: Only ServerSession object
**What dies after each request**: RequestContext and all its data

### Level 2: FastMCP Context

```python
# Created fresh for EACH request
class Context:
    def __init__(self):
        self._state: dict = {}  # EMPTY each request!
    
    @property
    def session_id(self) -> str:
        # Gets or creates ID on ServerSession
        session = self.request_context.session
        session_id = getattr(session, "_fastmcp_id", None)
        if not session_id:
            session_id = str(uuid4())
            setattr(session, "_fastmcp_id", session_id)  # PERSISTS on ServerSession!
        return session_id
```

**Request-scoped state** (via ctx._state):
```python
# Middleware sets data
ctx.set_state("phase_tracking", {"iteration": 2})
ctx.set_state("suggestions", ["Try deeper analysis"])

# Tool reads it
suggestions = ctx.get_state("suggestions")  # Works within same request

# Next request - ALL GONE!
suggestions = ctx.get_state("suggestions")  # None - new Context!
```

### Level 3: Your CompanionSessionManager

```python
class CompanionSessionManager:
    def __init__(self):
        self.sessions = {
            "abc-123": {  # session_id from FastMCP
                "companions": {
                    "generic": BaseCompanion(
                        history=[
                            HumanMessage("Analyze revenue"),
                            AIMessage("Revenue analysis..."),
                            HumanMessage("Go deeper"),
                            AIMessage("Deeper analysis...")
                        ],
                        run_log=[
                            {
                                "query": "Analyze revenue",
                                "draft": "Initial analysis...",
                                "critique": ["Need more depth", "Add examples"],
                                "revision": ["Deeper analysis...", "With examples..."]
                            }
                        ]
                    )
                },
                "created_at": datetime(2024, 1, 1),
                "last_accessed": datetime(2024, 1, 1, 10, 30)
            }
        }
```

**What persists across requests**: EVERYTHING in the sessions dict
**What dies on restart**: EVERYTHING - it's just Python memory

### Level 4: V2 Hybrid Storage

```python
# In-memory cache (hot data)
cache = {
    "abc-123": {...}  # Same structure as above
}

# Redis (persistent)
redis.get("session:abc-123") → {
    "companions": {
        "generic": {
            "type": "GenericCompanion",
            "history": [
                {"type": "human", "content": "Analyze revenue"},
                {"type": "ai", "content": "Revenue analysis..."}
            ],
            "run_log": [...],  # Already JSON-serializable
            "config": {
                "model_name": "gpt-4",
                "temperature": 0.7
            }
        }
    }
}
```

## Memory Flow Through Draft → Critique → Revise

Let's trace a complete reasoning cycle:

### Request 1: Draft

```python
# 1. Client calls draft tool
# 2. FastMCP creates Context (empty _state)
ctx.session_id  # "abc-123" from ServerSession._fastmcp_id

# 3. Tool gets companion
comp = session_manager.get_companion("abc-123", "generic")
# Initially: comp.run_log = []

# 4. Tool executes draft
draft = "Initial revenue analysis..."

# 5. Tool updates companion
comp.history.extend([
    HumanMessage("Analyze revenue"),
    AIMessage(draft)
])
comp.run_log.append({
    "query": "Analyze revenue",
    "draft": draft,
    "critique": [],  # Empty arrays
    "revision": []
})

# 6. Middleware might set request-scoped data
ctx.set_state("phase_tracking", {
    "phase": "draft",
    "iteration": 0,
    "timestamp": "2024-01-01T10:00:00"
})

# 7. V2: Background save to Redis
await redis.set("session:abc-123", serialize(session_data))

# 8. Response sent, Context destroyed
# But companion remains in session_manager.sessions["abc-123"]
```

### Request 2: Critique

```python
# 1. New request, NEW Context (empty _state)
ctx.session_id  # SAME "abc-123" from SAME ServerSession

# 2. Tool gets SAME companion
comp = session_manager.get_companion("abc-123", "generic")
# comp.run_log has draft from Request 1!

# 3. Critique sees draft via sliding window
window = last_n_drafts(comp, "Analyze revenue")
# Returns: "[ORIGINAL BASELINE]\nInitial revenue analysis..."

# 4. Generate critique
critique = "Needs more specific metrics and examples"

# 5. Update run_log arrays
comp.run_log[-1]["critique"].append(critique)
# Now: critique = ["Needs more specific metrics..."]

# 6. Middleware tracks iteration
ctx.set_state("phase_tracking", {
    "phase": "critique",
    "iteration": 1
})

# 7. V2: Background save
await redis.set("session:abc-123", serialize(session_data))
```

### Request 3: Revise

```python
# 1. New request, NEW Context again
ctx.session_id  # Still "abc-123"

# 2. Same companion with accumulated state
comp = session_manager.get_companion("abc-123", "generic")

# 3. Revise sees critique
current_critique = comp.run_log[-1]["critique"][-1]
# "Needs more specific metrics and examples"

# 4. Generate revision
revision = "Revenue increased 23% YoY with examples..."

# 5. Update arrays
comp.run_log[-1]["revision"].append(revision)
# Arrays now balanced: len(critique) == len(revision) == 1

# 6. Check convergence
similarity = calculate_similarity(draft, revision)  # 0.85
ctx.set_state("similarity_score", similarity)

# 7. V2: Background save
await redis.set("session:abc-123", serialize(session_data))
```

### Request 4: Critique 2

```python
# Arrays tell us where we are!
critiques = comp.run_log[-1]["critique"]  # Length 1
revisions = comp.run_log[-1]["revision"]  # Length 1
# Equal lengths → can critique again

# Sliding window now shows:
# "[ORIGINAL BASELINE]\nInitial revenue analysis..."
# "[ITERATION 1]\nRevenue increased 23% YoY with examples..."

critique2 = "Good improvement but add competitor comparison"
comp.run_log[-1]["critique"].append(critique2)
# Now: critique = ["Needs more...", "Good improvement..."]
```

## What Gets Stored Where

### Request-Scoped (ctx._state)
```python
# Dies after EACH request
ctx.set_state("phase_tracking", {...})      # Middleware communication
ctx.set_state("suggestions", [...])         # Intelligence hints
ctx.set_state("similarity_score", 0.95)     # Convergence metrics
ctx.set_state("timing", {"draft_ms": 1200}) # Performance data
```

### Session-Scoped (In Memory)
```python
# Survives across requests, dies on restart
session_manager.sessions["abc-123"] = {
    "companions": {
        "generic": BaseCompanion(...)  # Full Python object
    },
    "created_at": datetime.now(),
    "last_accessed": datetime.now()
}
```

### Persistent (Redis - V2)
```python
# Survives server restarts
redis["session:abc-123"] = {
    "companions": {
        "generic": {
            "type": "GenericCompanion",
            "history": [...],  # Serialized messages
            "run_log": [...],  # Already JSON
            "config": {...}    # Model settings
        }
    },
    "created_at": "2024-01-01T10:00:00",
    "last_accessed": "2024-01-01T11:00:00"
}
```

### Server-Scoped (Middleware)
```python
# Lives until server shutdown
class PhaseIntelligenceMiddleware:
    def __init__(self):
        self.global_metrics = {
            "avg_iterations_by_type": {
                "generic": [2, 3, 2, 4],      # Historical data
                "marketing": [2, 2, 3],
                "strategy": [3, 4, 3, 5]
            }
        }
```

## Context Flow Through Your Application

### 1. Request Initialization
```
MCP Request → SDK creates RequestContext → FastMCP creates Context
                                            ↓
                                    ctx.session_id retrieves "abc-123"
```

### 2. Middleware Enhancement
```
PhaseValidationMiddleware:
  → Reads companion from session_manager using ctx.session_id
  → Validates phase rules
  → Sets ctx.set_state("phase_valid", True)

PhaseIntelligenceMiddleware:
  → Analyzes companion state
  → Adds ctx.set_state("suggestions", [...])
  → Updates global_metrics
```

### 3. Tool Execution
```
Draft/Critique/Revise Tool:
  → Gets session_id from ctx
  → Retrieves companion from session_manager
  → Reads suggestions from ctx.get_state()
  → Modifies companion.history and companion.run_log
  → Returns structured output
```

### 4. Persistence (V2)
```
After tool execution:
  → Session marked dirty
  → Background task serializes companion
  → Saves to Redis without blocking response
```

## Persistence Strategy

### Why Redis First?
1. **Simple key-value** matches your session structure
2. **Fast** - in-memory with persistence
3. **TTL support** - automatic expiration
4. **Pub/sub** - can notify other servers of changes

```python
# Redis is perfect for session data
await redis.setex(
    f"session:{session_id}",
    ttl=3600 * 4,  # 4 hour TTL
    value=json.dumps(serialized_companion)
)
```

### PostgreSQL for Later
When you need:
1. **Complex queries** - "Find all sessions that used strategy companion"
2. **Analytics** - "Average iterations per companion type"
3. **Audit trails** - "Show all revisions for compliance"
4. **Long-term storage** - Years of data

```sql
-- Future PostgreSQL schema
CREATE TABLE sessions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP,
    last_accessed TIMESTAMP,
    companion_data JSONB,
    metadata JSONB
);

-- Complex queries become possible
SELECT 
    id,
    companion_data->'companions'->'generic'->'run_log'->0->>'query' as first_query,
    jsonb_array_length(companion_data->'companions'->'generic'->'run_log') as total_queries
FROM sessions
WHERE companion_data->'companions' ? 'strategy';
```

## The Complete Picture

Your system has elegant separation:
1. **MCP Protocol**: Stateless transport
2. **SDK**: Connection management
3. **FastMCP**: Request context + session identity
4. **Your SessionManager**: Actual state storage
5. **V2 Hybrid Storage**: Persistence without changing interfaces

The beauty is that each layer has exactly the right lifetime for its purpose, and the V2 proposal adds persistence without disrupting this clean architecture.