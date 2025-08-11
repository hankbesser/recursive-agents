"""
Session Persistence Layer for Recursive Agents MCP

This module provides optional Redis persistence for session data without
disrupting the existing in-memory session management. Falls back gracefully
to memory-only operation if Redis is unavailable.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import redis
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class SessionPersister:
    """
    Handles persistence of session data to Redis.
    
    This is an optional add-on that serializes companions and session state
    to JSON for storage in Redis. It handles:
    - Companion state (history, run_log, config)
    - Session metadata
    - Middleware state
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize the persister with optional Redis connection.
        
        Args:
            redis_url: Redis connection URL. If None, tries localhost:6379
        """
        try:
            if redis_url:
                self.redis = redis.from_url(redis_url, decode_responses=True)
            else:
                self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
            # Test connection
            self.redis.ping()
            self.enabled = True
            logger.info("Redis persistence enabled")
        except Exception as e:
            logger.warning(f"Redis not available, falling back to memory-only: {e}")
            self.redis = None
            self.enabled = False
    
    def save(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Save session data to Redis.
        
        Args:
            session_id: The session identifier
            session_data: Complete session data including companions
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            # Serialize the session data
            serialized = self._serialize_session(session_data)
            
            # Store in Redis with 24-hour TTL
            key = f"ra:session:{session_id}"
            self.redis.setex(
                key,
                86400,  # 24 hours in seconds
                json.dumps(serialized, default=str)
            )
            
            logger.debug(f"Saved session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False
    
    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session data from Redis.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Deserialized session data or None if not found
        """
        if not self.enabled:
            return None
            
        try:
            key = f"ra:session:{session_id}"
            data = self.redis.get(key)
            
            if not data:
                return None
            
            # Deserialize the session data
            serialized = json.loads(data)
            session = self._deserialize_session(serialized)
            
            logger.debug(f"Loaded session {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def delete(self, session_id: str) -> bool:
        """
        Delete session data from Redis.
        
        Args:
            session_id: The session identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            key = f"ra:session:{session_id}"
            self.redis.delete(key)
            logger.debug(f"Deleted session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def _serialize_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize session data for storage.
        
        Handles:
        - Datetime serialization
        - Companion serialization
        - LangChain message serialization
        """
        serialized = {
            "created_at": session_data["created_at"].isoformat() if isinstance(session_data["created_at"], datetime) else session_data["created_at"],
            "last_accessed": session_data["last_accessed"].isoformat() if isinstance(session_data["last_accessed"], datetime) else session_data["last_accessed"],
            "companions": {},
            "middleware_state": session_data.get("middleware_state", {})
        }
        
        # Serialize each companion
        for comp_type, companion in session_data.get("companions", {}).items():
            serialized["companions"][comp_type] = self._serialize_companion(companion)
        
        return serialized
    
    def _serialize_companion(self, companion) -> Dict[str, Any]:
        """
        Serialize a BaseCompanion instance.
        
        Args:
            companion: BaseCompanion instance
            
        Returns:
            JSON-serializable dictionary
        """
        return {
            "type": companion.__class__.__name__,
            "history": self._serialize_messages(companion.history),
            "run_log": companion.run_log,  # Already JSON-serializable
            "config": {
                "model_name": getattr(companion.llm, "model_name", None),
                "temperature": getattr(companion.llm, "temperature", None),
                "similarity_threshold": companion.similarity_threshold,
                "max_loops": companion.max_loops,
                "clear_history": companion.clear_history,
            },
            # Store any custom attributes we've added
            "custom_attrs": {
                "enable_similarity": getattr(companion, "enable_similarity", None),
                "preferred_execution_mode": getattr(companion, "preferred_execution_mode", None)
            }
        }
    
    def _serialize_messages(self, messages: List) -> List[Dict[str, Any]]:
        """
        Serialize LangChain messages to JSON.
        
        Args:
            messages: List of HumanMessage/AIMessage instances
            
        Returns:
            JSON-serializable list
        """
        serialized = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized.append({
                    "type": "human",
                    "content": msg.content
                })
            elif isinstance(msg, AIMessage):
                serialized.append({
                    "type": "ai",
                    "content": msg.content
                })
        return serialized
    
    def _deserialize_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize session data from storage.
        
        Args:
            data: Serialized session data
            
        Returns:
            Session data with proper Python objects
        """
        session = {
            "created_at": datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            "last_accessed": datetime.fromisoformat(data["last_accessed"]) if isinstance(data["last_accessed"], str) else data["last_accessed"],
            "companions": {},
            "middleware_state": data.get("middleware_state", {})
        }
        
        # Note: We don't deserialize companions here - that happens lazily
        # when they're actually needed. We just store the serialized data.
        session["_serialized_companions"] = data.get("companions", {})
        
        return session
    
    def deserialize_companion(self, comp_type: str, data: Dict[str, Any], companion_class):
        """
        Deserialize a companion from stored data.
        
        Args:
            comp_type: Type of companion
            data: Serialized companion data
            companion_class: Class to instantiate
            
        Returns:
            Restored BaseCompanion instance
        """
        config = data.get("config", {})
        
        # Create companion with stored config
        companion = companion_class(
            llm=config.get("model_name"),
            temperature=config.get("temperature"),
            similarity_threshold=config.get("similarity_threshold"),
            max_loops=config.get("max_loops"),
            clear_history=config.get("clear_history", False),
            verbose=False
        )
        
        # Restore history
        companion.history = self._deserialize_messages(data.get("history", []))
        
        # Restore run_log
        companion.run_log = data.get("run_log", [])
        
        # Restore custom attributes
        for attr, value in data.get("custom_attrs", {}).items():
            if value is not None:
                setattr(companion, attr, value)
        
        # Ensure streaming is enabled
        if hasattr(companion.llm, "streaming"):
            companion.llm.streaming = True
        
        return companion
    
    def _deserialize_messages(self, data: List[Dict[str, Any]]) -> List:
        """
        Deserialize LangChain messages from JSON.
        
        Args:
            data: Serialized message list
            
        Returns:
            List of HumanMessage/AIMessage instances
        """
        messages = []
        for msg_data in data:
            if msg_data["type"] == "human":
                messages.append(HumanMessage(content=msg_data["content"]))
            elif msg_data["type"] == "ai":
                messages.append(AIMessage(content=msg_data["content"]))
        return messages