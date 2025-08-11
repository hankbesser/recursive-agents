import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import uuid4

# ── Recursive Agents ---------------------------------------------------------
from core.chains import BaseCompanion
from recursive_agents.base import (
    GenericCompanion,
    MarketingCompanion,
    BugTriageCompanion,
    StrategyCompanion,
)

# ── Companion factory --------------------------------------------------------
COMPANION_MAP: Dict[str, type[BaseCompanion]] = {
    "generic": GenericCompanion,
    "marketing": MarketingCompanion,
    "bug_triage": BugTriageCompanion,
    "strategy": StrategyCompanion,
}

# ── Session Support -----------------------------------------------------------------
class CompanionSessionManager:
    def __init__(self, ttl_minutes: int = 30, cleanup_interval_minutes: int = 10, 
                 max_sessions_before_cleanup: int = 100, redis_url: str = None):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.max_sessions = max_sessions_before_cleanup
        self._cleanup_task = None
        self._lock = threading.Lock()  # Protect session operations (thread-safe)
        self._shutdown = False
        self._opportunistic_cleanup_running = False
        
        # Optional persistence layer
        try:
            from .session_persister import SessionPersister
            self.persister = SessionPersister(redis_url)
        except Exception as e:
            import logging
            logging.warning(f"Session persistence not available: {e}")
            self.persister = None

    def get_or_create_session(self, session_id: str = None) -> str:
        if not session_id:
            session_id = str(uuid4())

        now = datetime.now()
        if session_id not in self.sessions:
            # Try to load from persistence first
            loaded = False
            if self.persister:
                session_data = self.persister.load(session_id)
                if session_data:
                    self.sessions[session_id] = session_data
                    self.sessions[session_id]["last_accessed"] = now
                    loaded = True
            
            # Create new session if not loaded
            if not loaded:
                self.sessions[session_id] = {
                    "companions": {},
                    "middleware_state": {},  # For middleware to store cross-request data
                    "created_at": now,
                    "last_accessed": now,
                }
        else:
            # Update last accessed time
            self.sessions[session_id]["last_accessed"] = now
            
        # Opportunistic cleanup on new session creation
        if len(self.sessions) > self.max_sessions and not self._opportunistic_cleanup_running:
            self._opportunistic_cleanup_running = True
            asyncio.create_task(self._run_opportunistic_cleanup())
            
        return session_id

    def get_companion(self, session_id: str, companion_type: str, sampling_config=None) -> BaseCompanion:
        with self._lock:  # Use lock to prevent race conditions
            # Handle None or empty session_id
            if not session_id:
                session_id = self.get_or_create_session()
                
            # Ensure session exists before trying to get companion
            if session_id not in self.sessions:
                session_id = self.get_or_create_session(session_id)
            
            # Use .get() to avoid KeyError if session was just deleted
            session = self.sessions.get(session_id)
            if not session:
                # Session was deleted between check and access, recreate it
                session_id = self.get_or_create_session(session_id)
                session = self.sessions[session_id]
                
            session["last_accessed"] = datetime.now()  # Update activity
            companions = session["companions"]

            if companion_type not in companions:
                # Check if we have serialized companion data from persistence
                serialized_companions = session.get("_serialized_companions", {})
                if companion_type in serialized_companions and self.persister:
                    # Deserialize the companion from stored data
                    cls = COMPANION_MAP.get(companion_type.lower(), GenericCompanion)
                    comp = self.persister.deserialize_companion(
                        companion_type, 
                        serialized_companions[companion_type],
                        cls
                    )
                    companions[companion_type] = comp
                    # Remove from serialized data once deserialized
                    del serialized_companions[companion_type]
                else:
                    # Create new companion
                    cls = COMPANION_MAP.get(companion_type.lower(), GenericCompanion)
                    
                    # Extract params from sampling_config if provided
                    if sampling_config:
                        # Build kwargs only for non-None values
                        kwargs = {"verbose": False}
                        
                        if sampling_config.model is not None:
                            kwargs["llm"] = sampling_config.model
                        if sampling_config.temperature is not None:
                            kwargs["temperature"] = sampling_config.temperature
                        if sampling_config.similarity_threshold is not None:
                            kwargs["similarity_threshold"] = sampling_config.similarity_threshold
                        if sampling_config.max_loops is not None:
                            kwargs["max_loops"] = sampling_config.max_loops
                            
                        comp = cls(**kwargs)
                    else:
                        comp = cls(verbose=False)  # Use defaults
                        
                    # Set streaming on the LLM if supported
                    if hasattr(comp.llm, "streaming"):
                        comp.llm.streaming = True
                    companions[companion_type] = comp
                
                # Persist the session after creating/loading companion
                self._save_session(session_id)

            return companions[companion_type]
    
    def get_middleware_state(self, session_id: str) -> Dict[str, Any]:
        """Get middleware state for a session, creating session if needed."""
        if session_id not in self.sessions:
            self.get_or_create_session(session_id)
        return self.sessions[session_id].get("middleware_state", {})
    
    def set_middleware_state(self, session_id: str, key: str, value: Any):
        """Set a middleware state value for a session."""
        if session_id not in self.sessions:
            self.get_or_create_session(session_id)
        if "middleware_state" not in self.sessions[session_id]:
            self.sessions[session_id]["middleware_state"] = {}
        self.sessions[session_id]["middleware_state"][key] = value
        # Save session after middleware state update
        self._save_session(session_id)
    
    def _save_session(self, session_id: str):
        """Save session to persistence if available."""
        if self.persister and session_id in self.sessions:
            try:
                self.persister.save(session_id, self.sessions[session_id])
            except Exception as e:
                import logging
                logging.error(f"Failed to persist session {session_id}: {e}")
    
    def mark_companion_modified(self, session_id: str):
        """Mark that a companion was modified and trigger save."""
        self._save_session(session_id)
    
    def get_session_metadata(self, session_id: str):
        """Get metadata about a session for reporting."""
        session = self.sessions.get(session_id)
        if not session:
            return None
            
        # Calculate total iterations across all companions
        total_iterations = 0
        total_requests = 0
        
        for comp in session.get("companions", {}).values():
            if hasattr(comp, 'run_log'):
                total_requests += len(comp.run_log)
                # Sum up all critique arrays (each critique = 1 iteration)
                for slot in comp.run_log:
                    total_iterations += len(slot.get("critique", []))
        
        from schema.common import SessionMetadata
        return SessionMetadata(
            created_at=session.get("created_at", datetime.now()),
            last_accessed=session.get("last_accessed", datetime.now()),
            companion_types=list(session.get("companions", {}).keys()),
            total_iterations=total_iterations,
            total_requests=total_requests,
            current_phase=None  # Would need to track per companion
        )
    
    async def _run_opportunistic_cleanup(self):
        """Run cleanup and reset the flag."""
        try:
            await self.cleanup_expired_sessions()
        finally:
            self._opportunistic_cleanup_running = False
    
    async def cleanup_expired_sessions(self):
        """Remove sessions older than TTL that are not in use."""
        if self._shutdown:
            return
            
        async with self._lock:
            now = datetime.now()
            expired = []
            
            for sid, session in self.sessions.items():
                # Check if expired based on last access
                if now - session["last_accessed"] > self.ttl:
                    expired.append(sid)
            
            # Clean up expired sessions
            for sid in expired:
                session = self.sessions[sid]
                # Clean up each companion's resources
                for comp in session["companions"].values():
                    if hasattr(comp, 'history'):
                        comp.history.clear()
                    if hasattr(comp, 'run_log'):
                        comp.run_log.clear()
                    # If companion has other cleanup needs, add here
                
                del self.sessions[sid]
            
            if expired:
                # Use logging or a callback instead of print in production
                print(f"[SessionCleanup] Cleaned up {len(expired)} expired sessions")
    
    async def start_cleanup_task(self):
        """Start the periodic cleanup task."""
        async def periodic_cleanup():
            while not self._shutdown:
                try:
                    await asyncio.sleep(self.cleanup_interval.total_seconds())
                    await self.cleanup_expired_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Log error but continue running
                    print(f"[SessionCleanup] Error in periodic cleanup: {e}")
                    # In production, use proper logging
                    # logger.exception("Error in session cleanup task")
                    
        self._cleanup_task = asyncio.create_task(periodic_cleanup())
    
    async def shutdown(self):
        """Shutdown the session manager and clean up all resources."""
        self._shutdown = True
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clean up all sessions
        async with self._lock:
            for session in self.sessions.values():
                for comp in session["companions"].values():
                    if hasattr(comp, 'history'):
                        comp.history.clear()
                    if hasattr(comp, 'run_log'):
                        comp.run_log.clear()
            
            self.sessions.clear()

# Create the singleton instance
# Instantiate the session manager with optional Redis support
import os
redis_url = os.getenv("REDIS_URL")  # e.g., "redis://localhost:6379"
session_manager = CompanionSessionManager(ttl_minutes=30, redis_url=redis_url)

if redis_url:
    import logging
    logging.info(f"Session manager initialized with Redis persistence at {redis_url}")
else:
    import logging
    logging.info("Session manager initialized with memory-only storage (no Redis)")