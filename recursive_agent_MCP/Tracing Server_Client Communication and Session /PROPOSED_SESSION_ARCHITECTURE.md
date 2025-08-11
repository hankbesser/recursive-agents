# Proposed Session Architecture for Recursive Agents MCP

## Current State Analysis

After deeply tracing the entire stack from Python MCP SDK → FastMCP 2.11.1 → Your Implementation, here's what I understand:

### What You Currently Have

1. **CompanionSessionManager** (in-memory)
   - `sessions: Dict[str, Dict[str, BaseCompanion]]` - Companions by session/type
   - `metadata: Dict[str, SessionMetadata]` - Session tracking info
   - TTL-based cleanup with async locks
   - Opportunistic + periodic cleanup strategies

2. **Direct Companion Access in Tools**
   - Tools get companions via `session_manager.get_companion()`
   - Tools directly modify `comp.history` and `comp.run_log`
   - No middleware-based session loading/saving

3. **Schema Definitions**
   - Well-structured schemas (common, inputs, outputs)
   - SessionMetadata, RequestMetadata, IterationMetadata defined
   - But not fully utilized in middleware pattern

4. **Middleware**
   - PhaseValidationMiddleware - enforces phase rules
   - PhaseIntelligenceMiddleware - adds suggestions/metrics
   - But NO session persistence middleware

## The Core Issues

### 1. In-Memory Limitations
- Everything dies on server restart
- Can't scale horizontally (multiple server instances)
- Memory grows unbounded without proper eviction
- No persistence for valuable reasoning history

### 2. Tight Coupling
- Tools directly access CompanionSessionManager
- No abstraction layer for storage backend
- Hard to swap storage implementations

### 3. Missing Session Middleware
- FastMCP expects session state via middleware
- You're not following the recommended pattern
- State management is scattered across tools

## Proposed Architecture

### 1. Storage Backend Abstraction

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import json

class SessionStorageBackend(ABC):
    """Abstract base for session storage implementations"""
    
    @abstractmethod
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data"""
        pass
    
    @abstractmethod
    async def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store session data with optional TTL in seconds"""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Remove session data"""
        pass
    
    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """Check if session exists"""
        pass
```

### 2. Redis Storage Implementation

```python
import redis.asyncio as redis
from typing import Optional, Dict, Any
import json

class RedisSessionStorage(SessionStorageBackend):
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.prefix = "mcp:session:"
        
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = f"{self.prefix}{session_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        key = f"{self.prefix}{session_id}"
        serialized = json.dumps(data, default=str)  # Handle datetime serialization
        if ttl:
            await self.redis.setex(key, ttl, serialized)
        else:
            await self.redis.set(key, serialized)
    
    async def delete(self, session_id: str) -> None:
        key = f"{self.prefix}{session_id}"
        await self.redis.delete(key)
    
    async def exists(self, session_id: str) -> bool:
        key = f"{self.prefix}{session_id}"
        return bool(await self.redis.exists(key))
```

### 3. SQLAlchemy Storage Implementation

```python
from sqlalchemy import Column, String, JSON, DateTime, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class SessionModel(Base):
    __tablename__ = "mcp_sessions"
    
    id = Column(String, primary_key=True)
    data = Column(JSON)  # Or Text with manual JSON serialization
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class SQLAlchemySessionStorage(SessionStorageBackend):
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(SessionModel).where(
                    SessionModel.id == session_id,
                    or_(
                        SessionModel.expires_at.is_(None),
                        SessionModel.expires_at > datetime.utcnow()
                    )
                )
            )
            row = result.scalar_one_or_none()
            if row:
                return row.data
            return None
    
    async def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
        
        async with self.async_session() as session:
            # Upsert pattern
            stmt = insert(SessionModel).values(
                id=session_id,
                data=data,
                expires_at=expires_at
            ).on_conflict_do_update(
                index_elements=['id'],
                set_=dict(data=data, updated_at=datetime.utcnow(), expires_at=expires_at)
            )
            await session.execute(stmt)
            await session.commit()
```

### 4. Enhanced Session Manager

```python
from typing import Dict, Optional, Any, Type
from datetime import datetime
import pickle
import base64

class EnhancedSessionManager:
    """Manages companion sessions with pluggable storage backends"""
    
    def __init__(self, storage: SessionStorageBackend):
        self.storage = storage
        self._companion_classes: Dict[str, Type[BaseCompanion]] = {
            "generic": GenericCompanion,
            "marketing": MarketingCompanion,
            "bug_triage": BugTriageCompanion,
            "strategy": StrategyCompanion,
        }
    
    async def get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Get complete session data including all companions"""
        data = await self.storage.get(session_id)
        if not data:
            # Initialize new session
            data = {
                "created_at": datetime.utcnow().isoformat(),
                "companions": {},
                "metadata": {
                    "total_requests": 0,
                    "last_accessed": datetime.utcnow().isoformat()
                }
            }
            await self.storage.set(session_id, data)
        return data
    
    async def get_companion(
        self, 
        session_id: str, 
        companion_type: str,
        sampling_config: Optional[SamplingConfig] = None
    ) -> BaseCompanion:
        """Get or create companion instance"""
        
        # Get session data
        session_data = await self.get_session_data(session_id)
        companions_data = session_data.get("companions", {})
        
        # Check if companion exists in session
        if companion_type in companions_data:
            # Deserialize companion state
            comp_data = companions_data[companion_type]
            comp = self._deserialize_companion(companion_type, comp_data, sampling_config)
        else:
            # Create new companion
            comp = self._create_companion(companion_type, sampling_config)
            # Store initial state
            companions_data[companion_type] = self._serialize_companion(comp)
            session_data["companions"] = companions_data
            await self.storage.set(session_id, session_data)
        
        # Update last accessed
        session_data["metadata"]["last_accessed"] = datetime.utcnow().isoformat()
        
        return comp
    
    async def save_companion(
        self, 
        session_id: str, 
        companion_type: str, 
        companion: BaseCompanion
    ) -> None:
        """Save companion state back to storage"""
        session_data = await self.get_session_data(session_id)
        
        # Serialize and store companion
        session_data["companions"][companion_type] = self._serialize_companion(companion)
        
        # Update metadata
        session_data["metadata"]["last_accessed"] = datetime.utcnow().isoformat()
        session_data["metadata"]["total_requests"] = session_data["metadata"].get("total_requests", 0) + 1
        
        await self.storage.set(session_id, session_data)
    
    def _serialize_companion(self, comp: BaseCompanion) -> Dict[str, Any]:
        """Serialize companion state for storage"""
        return {
            "type": comp.__class__.__name__,
            "history": [
                {
                    "type": msg.__class__.__name__,
                    "content": msg.content
                }
                for msg in comp.history
            ],
            "run_log": comp.run_log,  # Already JSON-serializable
            "config": {
                "model_name": getattr(comp.llm, "model_name", None),
                "temperature": getattr(comp.llm, "temperature", None),
                "similarity_threshold": comp.similarity_threshold,
                "max_loops": comp.max_loops,
            }
        }
    
    def _deserialize_companion(
        self, 
        companion_type: str, 
        data: Dict[str, Any],
        sampling_config: Optional[SamplingConfig] = None
    ) -> BaseCompanion:
        """Recreate companion from stored state"""
        comp_class = self._companion_classes[companion_type]
        
        # Create companion with stored config
        config = data.get("config", {})
        comp = comp_class(
            llm=sampling_config.model if sampling_config else config.get("model_name"),
            temperature=sampling_config.temperature if sampling_config else config.get("temperature"),
            similarity_threshold=config.get("similarity_threshold"),
            max_loops=config.get("max_loops")
        )
        
        # Restore history
        comp.history = []
        for msg_data in data.get("history", []):
            if msg_data["type"] == "HumanMessage":
                comp.history.append(HumanMessage(content=msg_data["content"]))
            elif msg_data["type"] == "AIMessage":
                comp.history.append(AIMessage(content=msg_data["content"]))
        
        # Restore run_log
        comp.run_log = data.get("run_log", [])
        
        return comp
```

### 5. Session Middleware

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from typing import Dict, Any

class SessionMiddleware(Middleware):
    """Loads and saves session data for each request"""
    
    def __init__(self, session_manager: EnhancedSessionManager):
        self.session_manager = session_manager
        
    async def on_request(self, context: MiddlewareContext, call_next):
        """Load session before request, save after"""
        ctx = context.fastmcp_context
        if not ctx:
            return await call_next(context)
            
        session_id = ctx.session_id
        
        # Load session data into request context
        session_data = await self.session_manager.get_session_data(session_id)
        ctx.set_state("session_data", session_data)
        ctx.set_state("session_manager", self.session_manager)
        
        # Execute request
        result = await call_next(context)
        
        # Session saving is handled by tools after they modify companions
        # This is because only tools know which companions were modified
        
        return result
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Enhanced tool handling with automatic companion management"""
        ctx = context.fastmcp_context
        if not ctx:
            return await call_next(context)
        
        tool_name = context.message.name
        session_id = ctx.session_id
        
        # Determine companion type from tool
        companion_type = self._get_companion_type(tool_name)
        if companion_type:
            # Pre-load companion for the tool
            comp = await self.session_manager.get_companion(
                session_id, 
                companion_type
            )
            ctx.set_state("current_companion", comp)
            ctx.set_state("companion_type", companion_type)
        
        # Execute tool
        result = await call_next(context)
        
        # Auto-save companion if it was used
        if companion_type and ctx.get_state("companion_modified"):
            comp = ctx.get_state("current_companion")
            await self.session_manager.save_companion(
                session_id,
                companion_type,
                comp
            )
        
        return result
    
    def _get_companion_type(self, tool_name: str) -> Optional[str]:
        """Map tool names to companion types"""
        # This could be configurable
        tool_mapping = {
            "draft": "generic",  # Or read from tool params
            "critique": "generic",
            "revise": "generic",
            # Add more mappings
        }
        return tool_mapping.get(tool_name)
```

### 6. Modified Tool Pattern

```python
async def tool_draft(params: GenerateDraftInput, ctx: Context) -> DraftOutput:
    """Modified to use middleware-provided companion"""
    
    # Get companion from context (loaded by middleware)
    comp = ctx.get_state("current_companion")
    if not comp:
        # Fallback to direct access if middleware didn't load it
        session_manager = ctx.get_state("session_manager")
        comp = await session_manager.get_companion(
            ctx.session_id,
            params.companion_type,
            params.sampling
        )
    
    # Use companion as before
    chain = comp.init_chain.with_config(callbacks=[callback])
    draft = await chain.ainvoke({
        "user_input": params.query,
        "history": comp.history
    })
    
    # Update companion state
    comp.history.extend([HumanMessage(params.query), AIMessage(draft)])
    comp.run_log.append({
        "query": params.query,
        "draft": draft,
        "critique": [],
        "revision": [],
    })
    
    # Mark companion as modified so middleware saves it
    ctx.set_state("companion_modified", True)
    
    return DraftOutput(...)
```

## Migration Strategy

### Phase 1: Add Storage Backend
1. Implement SessionStorageBackend interface
2. Create Redis/SQLAlchemy implementations
3. Test storage operations

### Phase 2: Enhance Session Manager
1. Create EnhancedSessionManager
2. Add serialization/deserialization logic
3. Test with different storage backends

### Phase 3: Add Middleware
1. Implement SessionMiddleware
2. Configure companion type mappings
3. Test middleware with existing tools

### Phase 4: Gradual Tool Migration
1. Update tools to use middleware-provided companions
2. Add companion_modified flag where needed
3. Remove direct session_manager access

### Phase 5: Cleanup
1. Remove old CompanionSessionManager
2. Remove in-memory storage
3. Remove TTL/cleanup logic (handled by storage backend)

## Benefits of This Architecture

### 1. **Scalability**
- Horizontal scaling with Redis/PostgreSQL
- Session state shared across server instances
- No memory growth issues

### 2. **Persistence**
- Reasoning history survives server restarts
- Valuable companion data never lost
- Configurable TTLs at storage level

### 3. **Flexibility**
- Swap storage backends easily
- Add new storage implementations
- Configure per environment

### 4. **Clean Architecture**
- Clear separation of concerns
- Follows FastMCP patterns
- Easier to test and maintain

### 5. **Performance**
- Redis provides fast access
- SQLAlchemy for complex queries
- Caching strategies possible

## Configuration Example

```python
# config.py
from enum import Enum

class StorageBackend(Enum):
    MEMORY = "memory"
    REDIS = "redis"
    POSTGRESQL = "postgresql"

# Server initialization
storage_type = os.getenv("STORAGE_BACKEND", "redis")

if storage_type == StorageBackend.REDIS:
    storage = RedisSessionStorage(os.getenv("REDIS_URL"))
elif storage_type == StorageBackend.POSTGRESQL:
    storage = SQLAlchemySessionStorage(os.getenv("DATABASE_URL"))
else:
    storage = InMemorySessionStorage()  # For development

session_manager = EnhancedSessionManager(storage)
session_middleware = SessionMiddleware(session_manager)

mcp = FastMCP("Recursive Agents")
mcp.add_middleware(session_middleware)
mcp.add_middleware(PhaseValidationMiddleware(session_manager))
mcp.add_middleware(PhaseIntelligenceMiddleware())
```

## Next Steps

1. **Decide on primary storage backend** (Redis vs PostgreSQL)
2. **Design companion serialization format** (JSON vs pickle vs custom)
3. **Plan migration timeline** (can be done incrementally)
4. **Add monitoring/metrics** for session operations
5. **Consider caching layer** for frequently accessed sessions

This architecture aligns with FastMCP's design philosophy while providing the persistence and scalability your sophisticated reasoning system deserves.