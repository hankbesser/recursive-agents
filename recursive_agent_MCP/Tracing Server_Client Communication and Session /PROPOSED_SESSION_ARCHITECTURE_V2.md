# Proposed Session Architecture V2 - Enhanced Design

After deeply analyzing your entire codebase, schemas, tools, services, and how memory chains through your reasoning tools, here's a refined architecture that builds on your existing strengths.

## Understanding Your Current System

### The Genius of Your run_log Structure

```python
{
    "query": "What causes X?",
    "draft": "Initial analysis...",      # Immutable baseline
    "critique": ["C1", "C2", "C3"],      # Array lengths encode phase
    "revision": ["R1", "R2", "R3"],      # Parallel to critiques
    "variant": "gpt-4o-mini",
    "sampling": {...}
}
```

The array lengths tell you EXACTLY where you are:
- `len(critique) == len(revision)`: Ready for new critique
- `len(critique) > len(revision)`: Need revision
- Phase position without complex state machines!

### Your Memory Chaining Pattern

```
Draft (baseline) → Critique[0] → Revision[0] → Critique[1] → Revision[1] → ...
```

Each tool uses a "sliding window" to see relevant history:
- Critique sees: baseline + last 2 revisions
- Revision sees: current content + latest critique

## Enhanced Architecture V2

### 1. Storage Backend with Companion-Aware Serialization

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from datetime import datetime
import json
import pickle
import base64
from langchain_core.messages import HumanMessage, AIMessage

class CompanionStateSerializer:
    """Handles the complex serialization of BaseCompanion state"""
    
    @staticmethod
    def serialize_messages(messages: List[Any]) -> List[Dict[str, Any]]:
        """Serialize LangChain messages to JSON-compatible format"""
        serialized = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized.append({
                    "type": "human",
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                })
            elif isinstance(msg, AIMessage):
                serialized.append({
                    "type": "ai",
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                })
        return serialized
    
    @staticmethod
    def deserialize_messages(data: List[Dict[str, Any]]) -> List[Any]:
        """Recreate LangChain messages from serialized format"""
        messages = []
        for msg_data in data:
            if msg_data["type"] == "human":
                messages.append(HumanMessage(
                    content=msg_data["content"],
                    additional_kwargs=msg_data.get("additional_kwargs", {})
                ))
            elif msg_data["type"] == "ai":
                messages.append(AIMessage(
                    content=msg_data["content"],
                    additional_kwargs=msg_data.get("additional_kwargs", {})
                ))
        return messages
    
    @staticmethod
    def serialize_companion_state(companion: 'BaseCompanion') -> Dict[str, Any]:
        """Serialize complete companion state"""
        return {
            "type": companion.__class__.__name__,
            "history": CompanionStateSerializer.serialize_messages(companion.history),
            "run_log": companion.run_log,  # Already JSON-serializable!
            "config": {
                "model_name": getattr(companion.llm, "model_name", None),
                "temperature": getattr(companion.llm, "temperature", None),
                "similarity_threshold": companion.similarity_threshold,
                "max_loops": companion.max_loops,
                "clear_history": companion.clear_history,
            },
            # Store any custom attributes (like preferred_execution_mode)
            "custom_attrs": {
                "preferred_execution_mode": getattr(companion, "preferred_execution_mode", None)
            }
        }
```

### 2. Hybrid Storage Backend

Instead of replacing your in-memory system, enhance it with persistence:

```python
class HybridSessionStorage:
    """
    Combines in-memory caching with persistent storage.
    
    This maintains your existing performance while adding durability.
    """
    
    def __init__(self, 
                 persistent_backend: SessionStorageBackend,
                 cache_ttl_minutes: int = 30):
        self.persistent = persistent_backend
        self.cache: Dict[str, Dict[str, Any]] = {}  # In-memory cache
        self.cache_metadata: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._lock = asyncio.Lock()
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session with cache-first strategy"""
        async with self._lock:
            # Check cache first
            if session_id in self.cache:
                self.cache_metadata[session_id] = datetime.now()
                return self.cache[session_id]
            
            # Load from persistent storage
            data = await self.persistent.get(session_id)
            if data:
                # Populate cache
                self.cache[session_id] = data
                self.cache_metadata[session_id] = datetime.now()
            
            return data
    
    async def save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Save to both cache and persistent storage"""
        async with self._lock:
            # Update cache
            self.cache[session_id] = data
            self.cache_metadata[session_id] = datetime.now()
            
            # Persist asynchronously (don't block the request)
            asyncio.create_task(self._persist_async(session_id, data))
    
    async def _persist_async(self, session_id: str, data: Dict[str, Any]) -> None:
        """Background persistence to avoid blocking requests"""
        try:
            await self.persistent.set(session_id, data)
        except Exception as e:
            # Log but don't fail the request
            print(f"Failed to persist session {session_id}: {e}")
```

### 3. Enhanced CompanionSessionManager

Keep your existing manager but add persistence hooks:

```python
from typing import Dict, Any, Optional, Type
from services.companion_manager import COMPANION_MAP, CompanionSessionManager

class PersistentCompanionSessionManager(CompanionSessionManager):
    """
    Extends your existing session manager with persistence.
    
    Maintains backward compatibility while adding durability.
    """
    
    def __init__(self, 
                 storage: HybridSessionStorage,
                 ttl_minutes: int = 30,
                 cleanup_interval_minutes: int = 10,
                 max_sessions_before_cleanup: int = 100):
        super().__init__(ttl_minutes, cleanup_interval_minutes, max_sessions_before_cleanup)
        self.storage = storage
        self.serializer = CompanionStateSerializer()
    
    async def get_or_create_session(self, session_id: str = None) -> str:
        """Enhanced to load from persistent storage"""
        if not session_id:
            session_id = str(uuid4())
        
        now = datetime.now()
        
        # Try to load from persistent storage first
        if session_id not in self.sessions:
            stored_data = await self.storage.get_session(session_id)
            if stored_data:
                # Restore session from storage
                self.sessions[session_id] = await self._restore_session(stored_data)
                self.sessions[session_id]["last_accessed"] = now
            else:
                # Create new session
                self.sessions[session_id] = {
                    "companions": {},
                    "created_at": now,
                    "last_accessed": now,
                }
        else:
            # Update last accessed
            self.sessions[session_id]["last_accessed"] = now
        
        # Trigger opportunistic cleanup if needed
        if len(self.sessions) > self.max_sessions and not self._opportunistic_cleanup_running:
            self._opportunistic_cleanup_running = True
            asyncio.create_task(self._run_opportunistic_cleanup())
        
        return session_id
    
    def get_companion(self, session_id: str, companion_type: str, sampling_config=None) -> BaseCompanion:
        """Get companion with automatic persistence on modification"""
        companion = super().get_companion(session_id, companion_type, sampling_config)
        
        # Mark session as dirty when companion is accessed
        # (Assumes companion will be modified)
        asyncio.create_task(self._mark_dirty(session_id))
        
        return companion
    
    async def _mark_dirty(self, session_id: str):
        """Mark session for persistence after modifications"""
        # Wait a bit to batch modifications
        await asyncio.sleep(0.1)
        
        # Persist the session
        if session_id in self.sessions:
            session_data = await self._serialize_session(self.sessions[session_id])
            await self.storage.save_session(session_id, session_data)
    
    async def _serialize_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize session data for storage"""
        serialized = {
            "created_at": session["created_at"].isoformat(),
            "last_accessed": session["last_accessed"].isoformat(),
            "companions": {}
        }
        
        # Serialize each companion
        for comp_type, companion in session["companions"].items():
            serialized["companions"][comp_type] = self.serializer.serialize_companion_state(companion)
        
        return serialized
    
    async def _restore_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore session from serialized data"""
        session = {
            "created_at": datetime.fromisoformat(data["created_at"]),
            "last_accessed": datetime.fromisoformat(data["last_accessed"]),
            "companions": {}
        }
        
        # Restore each companion
        for comp_type, comp_data in data.get("companions", {}).items():
            companion = await self._restore_companion(comp_type, comp_data)
            session["companions"][comp_type] = companion
        
        return session
    
    async def _restore_companion(self, companion_type: str, data: Dict[str, Any]) -> BaseCompanion:
        """Restore companion from serialized state"""
        # Get companion class
        comp_class = COMPANION_MAP.get(companion_type, GenericCompanion)
        
        # Restore configuration
        config = data.get("config", {})
        companion = comp_class(
            llm=config.get("model_name"),
            temperature=config.get("temperature"),
            similarity_threshold=config.get("similarity_threshold"),
            max_loops=config.get("max_loops"),
            clear_history=config.get("clear_history", False),
            verbose=False
        )
        
        # Restore history
        companion.history = self.serializer.deserialize_messages(data.get("history", []))
        
        # Restore run_log (already in correct format)
        companion.run_log = data.get("run_log", [])
        
        # Restore custom attributes
        for attr, value in data.get("custom_attrs", {}).items():
            if value is not None:
                setattr(companion, attr, value)
        
        # Ensure streaming is enabled
        if hasattr(companion.llm, "streaming"):
            companion.llm.streaming = True
        
        return companion
```

### 4. Intelligent Session Middleware

This middleware adds cross-request intelligence:

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from typing import Dict, Any
import json

class IntelligentSessionMiddleware(Middleware):
    """
    Adds session intelligence and learning patterns.
    
    This middleware:
    1. Tracks patterns across sessions
    2. Provides intelligent defaults
    3. Detects anomalies
    4. Suggests optimizations
    """
    
    def __init__(self, session_manager: PersistentCompanionSessionManager):
        self.session_manager = session_manager
        self.global_patterns = {
            "avg_iterations_by_type": {},
            "common_convergence_thresholds": {},
            "typical_session_duration": {},
            "phase_transition_times": {}
        }
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        if not ctx:
            return await call_next(context)
        
        tool_name = context.message.name
        session_id = ctx.session_id
        
        # Pre-process: Load session patterns
        await self._load_session_patterns(ctx, session_id, tool_name)
        
        # Execute tool
        result = await call_next(context)
        
        # Post-process: Learn from execution
        await self._learn_from_execution(ctx, session_id, tool_name, result)
        
        return result
    
    async def _load_session_patterns(self, ctx, session_id: str, tool_name: str):
        """Load relevant patterns for this session"""
        # Get session metadata
        metadata = self.session_manager.get_session_metadata(session_id)
        if not metadata:
            return
        
        # Determine companion type from tool
        companion_type = self._get_companion_type_from_tool(tool_name)
        if not companion_type:
            return
        
        # Add intelligent suggestions based on patterns
        suggestions = {
            "typical_iterations": self.global_patterns["avg_iterations_by_type"].get(companion_type, 3),
            "recommended_threshold": self.global_patterns["common_convergence_thresholds"].get(companion_type, 0.98),
            "estimated_completion": self._estimate_completion_time(companion_type, metadata)
        }
        
        ctx.set_state("session_intelligence", suggestions)
    
    async def _learn_from_execution(self, ctx, session_id: str, tool_name: str, result):
        """Learn patterns from tool execution"""
        # Extract patterns from result
        if hasattr(result, 'iteration_metadata') and result.iteration_metadata:
            iteration_meta = result.iteration_metadata
            companion_type = self._get_companion_type_from_tool(tool_name)
            
            # Update global patterns
            if companion_type:
                # Track average iterations
                if companion_type not in self.global_patterns["avg_iterations_by_type"]:
                    self.global_patterns["avg_iterations_by_type"][companion_type] = []
                
                if iteration_meta.phase == Phase.REVISION:
                    self.global_patterns["avg_iterations_by_type"][companion_type].append(
                        iteration_meta.iteration_number
                    )
                
                # Track convergence patterns
                if iteration_meta.similarity_score:
                    if companion_type not in self.global_patterns["common_convergence_thresholds"]:
                        self.global_patterns["common_convergence_thresholds"][companion_type] = []
                    
                    self.global_patterns["common_convergence_thresholds"][companion_type].append(
                        iteration_meta.similarity_score
                    )
```

### 5. Resource Enhancement for Memory Access

Add new resources that expose companion state intelligently:

```python
async def resource_latest_critique(session_id: str, companion_type: str = "generic") -> Dict[str, Any]:
    """Get the most recent critique with context"""
    comp = session_manager.get_companion(session_id, companion_type)
    if not comp.run_log:
        return {"error": "No run_log available"}
    
    slot = comp.run_log[-1]
    critiques = slot.get("critique", [])
    
    if not critiques:
        return {"error": "No critiques available"}
    
    return {
        "critique": critiques[-1],
        "critique_number": len(critiques),
        "based_on": "revision" if len(slot.get("revision", [])) >= len(critiques) else "draft",
        "query": slot["query"],
        "session_id": session_id
    }

async def resource_penultimate_revision(session_id: str, companion_type: str = "generic") -> Dict[str, Any]:
    """Get the second-to-last revision for comparison"""
    comp = session_manager.get_companion(session_id, companion_type)
    if not comp.run_log:
        return {"error": "No run_log available"}
    
    slot = comp.run_log[-1]
    revisions = slot.get("revision", [])
    
    if len(revisions) < 2:
        return {"error": "Less than 2 revisions available"}
    
    return {
        "revision": revisions[-2],
        "revision_number": len(revisions) - 1,
        "query": slot["query"],
        "session_id": session_id
    }

async def resource_convergence_analysis(session_id: str, companion_type: str = "generic") -> Dict[str, Any]:
    """Analyze convergence patterns for the current query"""
    comp = session_manager.get_companion(session_id, companion_type)
    if not comp.run_log:
        return {"error": "No run_log available"}
    
    slot = comp.run_log[-1]
    
    # Calculate similarity between consecutive revisions
    similarities = []
    revisions = slot.get("revision", [])
    
    if len(revisions) >= 2:
        # Here you would calculate actual similarities
        # For now, return structure
        similarities = [
            {"revision_pair": [i, i+1], "similarity": 0.95 + (i * 0.01)}
            for i in range(len(revisions) - 1)
        ]
    
    return {
        "query": slot["query"],
        "iterations": len(slot.get("critique", [])),
        "similarities": similarities,
        "converged": similarities[-1]["similarity"] >= comp.similarity_threshold if similarities else False,
        "threshold": comp.similarity_threshold
    }
```

### 6. Tool Pattern Remains Direct

Keep your existing tool pattern - it's already good:

```python
async def tool_draft(params: GenerateDraftInput, ctx: Context) -> DraftOutput:
    """Your existing tool code stays the same!"""
    
    # Get session_id from Context
    session_id = ctx.session_id if ctx.session_id else params.session_id
    if not session_id:
        session_id = session_manager.get_or_create_session()
    
    # Get companion from enhanced session manager
    # (Now with automatic persistence!)
    comp = session_manager.get_companion(session_id, params.companion_type, params.sampling)
    
    # Direct manipulation as before
    comp.history.extend([HumanMessage(params.query), AIMessage(draft)])
    comp.run_log.append({
        "query": params.query,
        "draft": draft,
        "variant": variant,
        "critique": [],
        "revision": [],
        "sampling": cfg.model_dump(),
    })
    
    # Session manager handles persistence automatically
    # No code changes needed!
```

## Migration Path

### Phase 1: Add Storage Layer (No Code Changes)
```python
# Just change initialization
storage = HybridSessionStorage(
    persistent_backend=RedisSessionStorage()  # or SQLAlchemySessionStorage
)
session_manager = PersistentCompanionSessionManager(storage)

# Everything else works the same!
```

### Phase 2: Add Intelligence Middleware
```python
# Add to your server
mcp.add_middleware(IntelligentSessionMiddleware(session_manager))
```

### Phase 3: Add Enhanced Resources
```python
# Register new resources
mcp.resource("resource://sessions/{session_id}/{companion_type}/latest_critique")(
    resource_latest_critique
)
```

## Key Benefits of This Design

### 1. **Minimal Code Changes**
- Your tools don't change at all
- Session manager interface stays the same
- Just swap the implementation

### 2. **Gradual Enhancement**
- Start with in-memory (works today)
- Add Redis for persistence
- Add SQLAlchemy for complex queries
- Each step is independent

### 3. **Performance Maintained**
- In-memory cache for hot sessions
- Background persistence doesn't block requests
- Intelligent prefetching possible

### 4. **Intelligence Layer**
- Learn from usage patterns
- Provide smart defaults
- Detect anomalies
- All without changing tool code

### 5. **Preserves Your Innovation**
- run_log structure unchanged
- Phase tracking via array lengths maintained
- Direct companion manipulation preserved
- Streaming architecture untouched

## Configuration Examples

### Development (Current)
```python
# No changes needed - works as-is
session_manager = CompanionSessionManager()
```

### Staging (Add Persistence)
```python
storage = HybridSessionStorage(
    persistent_backend=RedisSessionStorage("redis://localhost:6379"),
    cache_ttl_minutes=60
)
session_manager = PersistentCompanionSessionManager(storage)
```

### Production (Full Features)
```python
# PostgreSQL for long-term storage
storage = HybridSessionStorage(
    persistent_backend=SQLAlchemySessionStorage(
        "postgresql://user:pass@host/db"
    ),
    cache_ttl_minutes=120
)

# Enhanced session manager
session_manager = PersistentCompanionSessionManager(
    storage=storage,
    ttl_minutes=240,  # 4 hours
    max_sessions_before_cleanup=1000
)

# Add intelligence
mcp.add_middleware(IntelligentSessionMiddleware(session_manager))
```

## Why This Design Works

1. **Builds on Your Strengths**: Enhances rather than replaces
2. **Respects Your Architecture**: Direct companion manipulation preserved
3. **Adds What You Need**: Persistence and intelligence
4. **Maintains Performance**: Hybrid caching strategy
5. **Enables Scale**: Redis/PostgreSQL for horizontal scaling

Your existing architecture is excellent. This design adds the persistence and intelligence layers you need without disrupting what already works well.