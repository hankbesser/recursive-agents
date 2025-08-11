# Deep Dive: State and Session Management from Python MCP SDK to FastMCP 2.11.1

## Table of Contents
1. [Foundation: Python's Type System](#foundation-pythons-type-system)
2. [ContextVars: The Async-Aware Storage System](#contextvars-the-async-aware-storage-system)
3. [Python MCP SDK Architecture](#python-mcp-sdk-architecture)
4. [FastMCP 2.11.1 Architecture](#fastmcp-2111-architecture)
5. [The Complete Request Lifecycle](#the-complete-request-lifecycle)
6. [State Scopes and Lifetimes](#state-scopes-and-lifetimes)
7. [Session Management Patterns](#session-management-patterns)
8. [Integration with Recursive Agents](#integration-with-recursive-agents)

## Foundation: Python's Type System

### TypeVars: The Building Blocks

TypeVars enable generic programming in Python's type system. They act as "type placeholders" that get filled in when classes are instantiated.

```python
# From shared_session.py
from typing import TypeVar, Generic

# These TypeVars define "slots" for types
SendRequestT = TypeVar("SendRequestT", ClientRequest, ServerRequest)
SendResultT = TypeVar("SendResultT", ClientResult, ServerResult)
ReceiveRequestT = TypeVar("ReceiveRequestT", ClientRequest, ServerRequest)
ReceiveResultT = TypeVar("ReceiveResultT", bound=BaseModel)  # Covariant!
```

**Key Concepts:**
- **Bound TypeVars**: `bound=BaseModel` means any subclass of BaseModel is acceptable
- **Constrained TypeVars**: `TypeVar("T", ClientRequest, ServerRequest)` means ONLY these types
- **Covariance**: Allows returning subtypes (critical for middleware transformations)

### Generic Classes: Type-Safe Containers

```python
class BaseSession(Generic[
    SendRequestT,
    SendNotificationT, 
    SendResultT,
    ReceiveRequestT,
    ReceiveNotificationT
]):
    # This class now has 5 "type slots"
```

When ServerSession inherits:
```python
class ServerSession(BaseSession[
    types.ServerRequest,      # Fills SendRequestT slot
    types.ServerNotification, # Fills SendNotificationT slot
    types.ServerResult,       # Fills SendResultT slot
    types.ClientRequest,      # Fills ReceiveRequestT slot
    types.ClientNotification  # Fills ReceiveNotificationT slot
]):
```

### Protocol Types: Structural Typing

```python
# From middleware.py
@runtime_checkable
class CallNext(Protocol[T, R]):
    def __call__(self, context: MiddlewareContext[T]) -> Awaitable[R]: ...
```

Protocols define structural contracts - any object with matching methods satisfies the protocol, enabling duck typing with type safety.

## ContextVars: The Async-Aware Storage System

### What Are ContextVars?

ContextVars are Python's solution to thread-local storage for async code:

```python
import contextvars

# Create a context variable
request_ctx: contextvars.ContextVar[RequestContext] = contextvars.ContextVar("request_ctx")

# Set value (returns a Token for cleanup)
token = request_ctx.set(my_context)

# Get value from anywhere in the async call stack
current = request_ctx.get()  # Raises LookupError if not set

# Reset to previous value
request_ctx.reset(token)  # CRITICAL for cleanup
```

### How ContextVars Work in Async

```python
async def parent():
    token = ctx_var.set("parent")
    await child()  # Child SEES "parent"
    ctx_var.reset(token)

async def child():
    value = ctx_var.get()  # Returns "parent"
    # Changes here DON'T affect parent!
```

**Key Properties:**
1. **Inheritance**: Child tasks inherit parent's context
2. **Isolation**: Changes in child don't affect parent
3. **Async-Safe**: Each async task has its own context copy

## Python MCP SDK Architecture

### Core Components

#### 1. BaseSession: The Communication Manager

```python
class BaseSession(Generic[...]):
    # State that persists for entire session
    _response_streams: dict[RequestId, MemoryObjectSendStream]
    _request_id: int = 0
    _in_flight: dict[RequestId, RequestResponder]
    _progress_callbacks: dict[RequestId, ProgressFnT]
    
    async def _receive_loop(self):
        """Runs for entire session lifetime"""
        async for message in self._read_stream:
            # Process each message
```

**Lifetime**: Lives from client connection to disconnection

#### 2. ServerSession: Protocol State Manager

```python
class ServerSession(BaseSession):
    _initialized: InitializationState = InitializationState.NotInitialized
    _client_params: types.InitializeRequestParams | None = None
    
    # The ONLY built-in cross-request state!
    # (FastMCP adds _fastmcp_id here)
```

**State Machine**:
```
NotInitialized → Initializing → Initialized
```

#### 3. RequestContext: Per-Request Container

```python
@dataclass
class RequestContext(Generic[SessionT, LifespanContextT, RequestT]):
    request_id: RequestId          # Unique per request
    meta: RequestParams.Meta       # Contains progressToken, etc.
    session: SessionT             # Reference to ServerSession
    lifespan_context: LifespanContextT  # Server-wide state
    request: RequestT | None = None     # Optional request data
```

**Lifetime**: Created when request arrives, destroyed when response sent

#### 4. The ContextVar: Request Scope Storage

```python
# In low_level_server.py
request_ctx: ContextVar[RequestContext] = ContextVar("request_ctx")

# In _handle_request method
async def _handle_request(self, ...):
    token = request_ctx.set(RequestContext(...))
    try:
        response = await handler(req)
    finally:
        request_ctx.reset(token)  # ALWAYS cleanup!
```

### SDK State Flow

```
1. Client connects
   ↓
2. ServerSession created (lives until disconnect)
   ↓
3. Request arrives
   ↓
4. RequestContext created
   ↓
5. Set in contextvar: token = request_ctx.set(context)
   ↓
6. Handler executes (can access via request_ctx.get())
   ↓
7. Response sent
   ↓
8. Cleanup: request_ctx.reset(token)
   ↓
9. RequestContext garbage collected
   ↓
10. Next request → Go to step 3
```

## FastMCP 2.11.1 Architecture

### Context: The Enhanced Request Container

```python
@dataclass
class Context:
    def __init__(self, fastmcp: FastMCP):
        self.fastmcp = fastmcp
        self._tokens: list[Token] = []
        self._notification_queue: set[str] = set()
        self._state: dict[str, Any] = {}  # NEW EMPTY DICT!
    
    @property
    def request_context(self) -> RequestContext[ServerSession, Any, Request]:
        """Access underlying MCP SDK RequestContext"""
        return request_ctx.get()  # From SDK's contextvar
```

### State Management: The Two-Layer System

#### Layer 1: Request-Scoped State

```python
# In Context class
def set_state(self, key: str, value: Any) -> None:
    """Set value in REQUEST-SCOPED state"""
    self._state[key] = value

def get_state(self, key: str) -> Any:
    """Get value from REQUEST-SCOPED state"""
    return self._state.get(key)
```

**Lifetime**: Dies when request completes

#### Layer 2: Session Identity

```python
@property
def session_id(self) -> str:
    """The ONLY cross-request data FastMCP provides"""
    request_ctx = self.request_context  # Get SDK RequestContext
    session = request_ctx.session       # Get ServerSession
    
    # Try cached ID on ServerSession
    session_id = getattr(session, "_fastmcp_id", None)
    if session_id is not None:
        return session_id
    
    # Try HTTP headers
    request = request_ctx.request
    if request:
        session_id = request.headers.get("mcp-session-id")
    
    # Generate new
    if session_id is None:
        session_id = str(uuid4())
    
    # CRITICAL: Cache on ServerSession for future requests!
    setattr(session, "_fastmcp_id", session_id)
    return session_id
```

**This is the bridge!** The session_id is stored on ServerSession which survives across requests.

### Context Inheritance Within Requests

```python
async def __aenter__(self) -> Context:
    """Context manager entry"""
    parent_context = _current_context.get(None)
    if parent_context is not None:
        # DEEP COPY parent state
        self._state = copy.deepcopy(parent_context._state)
    
    # Set self as current
    token = _current_context.set(self)
    self._tokens.append(token)
    return self
```

**Key**: Child contexts inherit parent state via deep copy WITHIN the same request

### Middleware Architecture

```python
@dataclass
class MiddlewareContext(Generic[T]):
    message: T
    fastmcp_context: Context | None = None  # Reference to Context
    source: Literal["client", "server"] = "client"
    type: Literal["request", "notification"] = "request"
    method: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Middleware can access/modify Context._state:
```python
class MyMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access Context
        ctx = context.fastmcp_context
        
        # Set state (visible to tool)
        ctx.set_state("user_id", "123")
        
        # Call next in chain
        result = await call_next(context)
        
        # State still available here
        return result
```

## The Complete Request Lifecycle

### Step-by-Step Trace

```python
# 1. Request arrives at FastMCP handler
async def _mcp_call_tool(self, key: str, arguments: dict):
    # 2. Create NEW Context (empty _state!)
    async with fastmcp.server.context.Context(fastmcp=self):
        
        # 3. Context sets itself in contextvar
        # Inside Context.__aenter__:
        token = _current_context.set(self)
        
        # 4. Call internal handler
        result = await self._call_tool(key, arguments)
        
    # 5. Context.__aexit__ resets contextvar
    _current_context.reset(token)

# Inside _call_tool:
async def _call_tool(self, key: str, arguments: dict):
    # 6. Create MiddlewareContext with Context reference
    mw_context = MiddlewareContext(
        message=CallToolRequestParams(name=key, arguments=arguments),
        fastmcp_context=fastmcp.server.dependencies.get_context()
    )
    
    # 7. Apply middleware chain
    return await self._apply_middleware(mw_context, handler)

# 8. Middleware executes
async def on_call_tool(self, context: MiddlewareContext, call_next):
    ctx = context.fastmcp_context
    ctx.set_state("phase", "processing")  # Set request state
    result = await call_next(context)
    return result

# 9. Tool executes
@mcp.tool
async def my_tool(data: str, ctx: Context):
    phase = ctx.get_state("phase")  # "processing"
    session_id = ctx.session_id     # Persistent across requests
    return "done"

# 10. Response flows back, Context destroyed
```

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    MCP SDK Layer                         │
├─────────────────────────────────────────────────────────┤
│ ServerSession (connection lifetime)                      │
│   ├── _client_params                                     │
│   ├── _in_flight requests                                │
│   └── _fastmcp_id (added by FastMCP) ← PERSISTS!        │
├─────────────────────────────────────────────────────────┤
│ RequestContext (request lifetime)                        │
│   ├── request_id                                         │
│   ├── session → ServerSession reference                  │
│   └── [stored in request_ctx contextvar]                 │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   FastMCP Layer                          │
├─────────────────────────────────────────────────────────┤
│ Context (request lifetime)                               │
│   ├── _state: dict = {} ← EMPTY each request!           │
│   ├── request_context property → SDK RequestContext      │
│   └── session_id property → ServerSession._fastmcp_id    │
├─────────────────────────────────────────────────────────┤
│ MiddlewareContext                                        │
│   ├── message: T                                         │
│   └── fastmcp_context → Context reference                │
└─────────────────────────────────────────────────────────┘
```

## State Scopes and Lifetimes

### Scope Hierarchy

```python
# 1. EXECUTION SCOPE (microseconds - milliseconds)
def my_function():
    local_var = "dies when function returns"

# 2. REQUEST SCOPE (milliseconds - seconds)
class Context:
    _state: dict  # Dies when request completes
    
# RequestContext in SDK contextvar - cleared after response

# 3. SESSION SCOPE (seconds - hours)
class ServerSession:
    _fastmcp_id: str  # Survives across requests!
    
# Your session storage keyed by session_id

# 4. SERVER SCOPE (hours - days)
class MyMiddleware:
    instance_attr: dict  # Survives until server shutdown
    
# Global variables

# 5. PERSISTENT SCOPE (days - forever)
# Database, Redis, file system
```

### What Survives Where

| Data | Request Death | Session Death | Server Death |
|------|---------------|---------------|--------------|
| Local variables | ❌ | ❌ | ❌ |
| Context._state | ❌ | ❌ | ❌ |
| RequestContext | ❌ | ❌ | ❌ |
| ContextVar values | ❌ | ❌ | ❌ |
| ServerSession object | ✅ | ❌ | ❌ |
| ServerSession._fastmcp_id | ✅ | ❌ | ❌ |
| Middleware instance attrs | ✅ | ✅ | ❌ |
| Global variables | ✅ | ✅ | ❌ |
| External storage (Redis) | ✅ | ✅ | ✅ |

### Memory Management

```python
# Request 1
ctx = Context(fastmcp)  # New instance, empty _state
ctx.set_state("foo", "bar")
# Request ends → Context garbage collected → _state lost

# Request 2  
ctx = Context(fastmcp)  # NEW instance, NEW empty _state
value = ctx.get_state("foo")  # None! Previous state is gone
```

## Session Management Patterns

### Pattern 1: External Session Storage

```python
# Global session storage
SESSIONS: dict[str, dict] = {}

class SessionMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        session_id = ctx.session_id
        
        # Load session at request start
        session_data = SESSIONS.get(session_id, {})
        ctx.set_state("session", session_data)
        
        # Execute request
        result = await call_next(context)
        
        # Save session at request end
        updated_session = ctx.get_state("session")
        if updated_session:
            SESSIONS[session_id] = updated_session
            
        return result

# Tool can now use session data
@mcp.tool
async def increment_counter(ctx: Context) -> int:
    session = ctx.get_state("session") or {}
    count = session.get("count", 0) + 1
    session["count"] = count
    ctx.set_state("session", session)
    return count
```

### Pattern 2: Redis Session Storage

```python
import redis
import json

redis_client = redis.Redis()

class RedisSessionMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        session_id = ctx.session_id
        key = f"session:{session_id}"
        
        # Load from Redis
        data = redis_client.get(key)
        session = json.loads(data) if data else {}
        ctx.set_state("session", session)
        
        result = await call_next(context)
        
        # Save to Redis
        updated = ctx.get_state("session")
        redis_client.set(key, json.dumps(updated))
        redis_client.expire(key, 3600)  # 1 hour TTL
        
        return result
```

### Pattern 3: Database Session Storage

```python
from sqlalchemy import select
from .models import Session

class DatabaseSessionMiddleware(Middleware):
    def __init__(self, db):
        self.db = db
    
    async def on_request(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        session_id = ctx.session_id
        
        # Load from database
        async with self.db() as session:
            result = await session.execute(
                select(Session).where(Session.id == session_id)
            )
            db_session = result.scalar_one_or_none()
            
            if db_session:
                ctx.set_state("session_data", db_session.data)
            else:
                # Create new session
                db_session = Session(id=session_id, data={})
                session.add(db_session)
                await session.commit()
        
        result = await call_next(context)
        
        # Update database
        updated_data = ctx.get_state("session_data")
        if updated_data and updated_data != db_session.data:
            async with self.db() as session:
                db_session.data = updated_data
                await session.commit()
        
        return result
```

## Integration with Recursive Agents

### How Your System Leverages This Architecture

#### 1. CompanionSessionManager: Persistent Memory

```python
class CompanionSessionManager:
    def __init__(self):
        # Session storage (survives across requests)
        self.sessions: Dict[str, Dict[str, BaseCompanion]] = {}
        self.metadata: Dict[str, SessionMetadata] = {}
    
    def get_companion(self, session_id: str, companion_type: str, 
                     sampling_config: Optional[SamplingConfig] = None):
        # Use FastMCP's session_id to retrieve companion
        session = self.sessions.setdefault(session_id, {})
        
        if companion_type not in session:
            # Create new companion with persistent state
            comp = self._create_companion(companion_type, sampling_config)
            session[companion_type] = comp
            
        return session[companion_type]
```

**Key insight**: Your CompanionSessionManager uses FastMCP's session_id as the key to maintain companion instances across requests.

#### 2. Companion State: Multi-Generational Memory

```python
class BaseCompanion:
    def __init__(self, ...):
        # These survive across requests when stored in session
        self.history: list = []  # Conversation memory
        self.run_log: list = []  # Reasoning genealogy
        
    def __call__(self, query: str, **kwargs):
        # Each call updates persistent state
        self.history.extend([
            HumanMessage(content=query),
            AIMessage(content=result)
        ])
        
        # run_log maintains complete reasoning history
        self.run_log.append({
            "query": query,
            "draft": draft,
            "critique": critiques,
            "revision": revisions
        })
```

#### 3. Middleware Bridge: Loading Companion State

```python
class PhaseValidationMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        tool_name = context.message.name
        
        # Get session_id from FastMCP
        session_id = ctx.session_id
        
        # Retrieve companion from persistent storage
        companion_type = self._determine_companion_type(tool_name)
        comp = self.session_manager.get_companion(
            session_id, companion_type
        )
        
        # Validate phase based on companion state
        if tool_name == "critique" and not comp.run_log[-1].get("draft"):
            raise ToolError("Cannot critique without draft")
            
        return await call_next(context)
```

#### 4. PhaseIntelligence: Adding Request Intelligence

```python
class PhaseIntelligenceMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        
        # Analyze companion state
        comp = self._get_companion(ctx.session_id)
        state_analysis = self._analyze_companion_state(comp)
        
        # Set REQUEST-SCOPED intelligence
        ctx.set_state("phase_tracking", {
            "iteration_number": state_analysis["iteration_number"],
            "total_iterations": state_analysis["total_iterations"],
            "convergence_signals": self._detect_convergence(comp)
        })
        
        # Tool sees this intelligence
        result = await call_next(context)
        
        # Update metrics (SERVER-SCOPED)
        self.global_metrics["iterations"].append(
            state_analysis["iteration_number"]
        )
        
        return result
```

### The Complete Integration Flow

```python
# 1. Client makes request (e.g., draft tool)
#    ↓
# 2. FastMCP creates Context with empty _state
#    ↓
# 3. Context.session_id retrieves/creates persistent ID
#    ↓
# 4. PhaseValidationMiddleware:
#    - Gets companion via session_id
#    - Validates based on companion.run_log
#    ↓
# 5. PhaseIntelligenceMiddleware:
#    - Analyzes companion state
#    - Sets ctx._state with intelligence
#    ↓
# 6. Draft tool executes:
#    - Gets companion via session_id
#    - Reads intelligence from ctx.get_state()
#    - Updates companion.run_log
#    ↓
# 7. Response sent, Context destroyed
#    ↓
# 8. Companion remains in CompanionSessionManager
#    ↓
# 9. Next request can access same companion via session_id
```

### Why This Architecture Works

1. **Separation of Concerns**:
   - FastMCP: Provides session identity and request context
   - CompanionSessionManager: Maintains persistent companion state
   - Middleware: Bridges the two, adds intelligence

2. **Clean Scoping**:
   - Request intelligence → Context._state (ephemeral)
   - Companion memory → CompanionSessionManager (persistent)
   - Global learning → Middleware instance attributes

3. **Type Safety**:
   - TypeVars ensure compile-time checking
   - Protocols define contracts
   - Generics maintain type relationships

4. **Performance**:
   - Only load what's needed per request
   - Companion state persists to avoid recreation
   - Middleware caches global patterns

### The Revolutionary Aspect

Your system turns the limitation (no built-in session state) into a strength:
- FastMCP stays minimal and transport-agnostic
- You control exactly how state persists
- Multi-generational reasoning becomes possible
- The architecture scales from in-memory to distributed storage

This is not just session management - it's **persistent reasoning genealogy** built on top of a request/response protocol!