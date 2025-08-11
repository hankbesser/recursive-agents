# schema/common.py
"""
Common types and base models for Recursive Agents MCP Server.

This module defines shared types, enums, and base classes used across
all tool inputs and outputs. It serves as the foundation for the 
MCP protocol implementation.
"""

from typing import Literal, Annotated, Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# =====================================================================
# COMPANION TYPES
# =====================================================================

COMPANION_TYPES = Literal["generic", "marketing", "bug_triage", "strategy"]
"""Available companion types that map to BaseCompanion subclasses."""


# =====================================================================
# SERVER MODELS  
# =====================================================================

SERVER_MODELS = Literal[
    "gpt-4o-mini",
    "gpt-4o", 
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo"
]
"""OpenAI models available on the MCP server for server-side execution."""


# =====================================================================
# EXECUTION MODES
# =====================================================================

class ExecutionMode(str, Enum):
    """Where the LLM execution happens."""
    CLIENT = "client"  # Client's own model (Claude, local LLM, etc.)
    SERVER = "server"  # Server's OpenAI model


# =====================================================================
# SAMPLING CONFIGURATION
# =====================================================================

class SamplingConfig(BaseModel):
    """
    LLM sampling configuration that flows to BaseCompanion initialization.
    
    This configuration is separated into three concerns:
    1. Execution location (client vs server) - determines where LLM runs
    2. Model configuration - which model and how to call it
    3. Convergence parameters - BaseCompanion's iterative improvement settings
    
    For new queries/variants, these can be elicited from the user.
    For critique/revision phases, they're inherited from the initial draft.
    """
    
    # === EXECUTION LOCATION ===
    execution_mode: Annotated[
        Optional[ExecutionMode],
        "Where to execute: 'client' or 'server'. None to ask user."
    ] = Field(
        default=None,
        description="Determines if LLM runs on MCP client or server"
    )
    
    # === MODEL CONFIGURATION ===
    model: Annotated[
        Optional[str],
        "Model identifier (e.g., 'gpt-4o-mini', 'claude-3-opus')"
    ] = Field(
        default=None,
        description="For server mode: which model to use. For client mode: hint for model preference."
    )
    
    temperature: Annotated[
        Optional[float],
        "Sampling temperature (0.0-2.0). Lower = focused, higher = creative"
    ] = Field(default=None, ge=0.0, le=2.0)
    
    max_tokens: Annotated[
        Optional[int],
        "Maximum tokens to generate"
    ] = Field(default=None, gt=0, le=128000)
    
    # === CONVERGENCE PARAMETERS (BaseCompanion) ===
    similarity_threshold: Annotated[
        Optional[float],
        "Cosine similarity threshold for convergence (0.90-0.99)"
    ] = Field(
        default=None, 
        ge=0.90, 
        le=0.99,
        description="When consecutive revisions are this similar, stop iterating. Default: 0.98"
    )
    
    max_loops: Annotated[
        Optional[int],
        "Maximum critique-revision cycles before stopping (1-10)"
    ] = Field(
        default=None,
        ge=1,
        le=10,
        description="Hard limit on iterations. Default: 3"
    )
    
    # === ADVANCED OPTIONS ===
    stop_sequences: Annotated[
        Optional[List[str]],
        "Sequences that stop generation"
    ] = None
    
    # Model preferences for client-side execution (MCP protocol feature)
    # This could include multiple model hints, cost/speed preferences, etc.
    # We use Dict for now to avoid importing MCP types here
    model_preferences: Annotated[
        Optional[Dict[str, Any]],
        "Advanced model preferences for client-side execution (MCP ModelPreferences)"
    ] = None
    
    # Additional parameters for future features
    metadata: Annotated[
        Optional[Dict[str, Any]],
        "Additional parameters for future features"
    ] = None
    
    # Backward compatibility helper
    @property
    def use_client_sampling(self) -> Optional[bool]:
        """Legacy property for backward compatibility."""
        if self.execution_mode is None:
            return None
        return self.execution_mode == ExecutionMode.CLIENT


# =====================================================================
# PHASE TRACKING
# =====================================================================

class Phase(str, Enum):
    """Which phase of the three-phase cycle."""
    DRAFT = "draft"
    CRITIQUE = "critique"
    REVISION = "revision"


# =====================================================================
# METADATA TYPES (must be defined before BaseToolOutput uses them)
# =====================================================================

class RequestMetadata(BaseModel):
    """
    Request-level metadata from FastMCP context.
    
    This captures ephemeral, request-scoped information that flows
    through the middleware pipeline. It's populated from ctx (Context)
    and includes MCP protocol details.
    """
    request_id: str = Field(
        description="Unique request ID from MCP protocol"
    )
    client_id: Optional[str] = Field(
        default=None,
        description="Client identifier if available"
    )
    session_id: str = Field(
        description="Session ID (from context fallback chain)"
    )
    progress_token: Optional[Union[str, int]] = Field(
        default=None,
        description="Progress token for reporting progress back to client"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="When this request was processed"
    )


class SessionMetadata(BaseModel):
    """
    Session-level metadata from CompanionSessionManager.
    
    This captures persistent, session-scoped information that survives
    across multiple requests. It's maintained by the session manager
    and tracks companion usage patterns.
    """
    created_at: datetime = Field(
        description="When this session was first created"
    )
    last_accessed: datetime = Field(
        description="Last time this session was accessed"
    )
    companion_types: List[str] = Field(
        default_factory=list,
        description="All companion types used in this session"
    )
    total_iterations: int = Field(
        default=0,
        description="Total critique-revision cycles across all queries"
    )
    total_requests: int = Field(
        default=0,
        description="Total number of tool requests in this session"
    )
    current_phase: Optional[Phase] = Field(
        default=None,
        description="Current phase in the recursive cycle"
    )


class IterationMetadata(BaseModel):
    """
    Iteration-level metadata for tracking convergence.
    
    This captures information about the current iteration within
    a recursive improvement cycle, helping track convergence and
    provide intelligent suggestions.
    """
    iteration_number: int = Field(
        description="Current iteration (1-based)"
    )
    phase: Phase = Field(
        description="Current phase: draft, critique, or revision"
    )
    similarity_score: Optional[float] = Field(
        default=None,
        description="Cosine similarity to previous iteration (if applicable)"
    )
    convergence_hints: List[str] = Field(
        default_factory=list,
        description="Suggestions from middleware about convergence"
    )
    elapsed_ms: Optional[int] = Field(
        default=None,
        description="Time taken for this iteration in milliseconds"
    )


# =====================================================================
# BASE CLASSES
# =====================================================================

class BaseToolInput(BaseModel):
    """
    Base input model with common fields for all tools.
    
    All tools share these parameters for session management
    and companion selection.
    """
    companion_type: COMPANION_TYPES = Field(
        default="generic",
        description="Type of companion to use for analysis"
    )
    
    session_id: Annotated[
        Optional[str],
        "Session ID (UUID v4) for conversation continuity. Auto-generated if not provided."
    ] = Field(default=None)
    
    # Note: session_id validation is in inputs.py to avoid circular imports


class BaseToolOutput(BaseModel):
    """
    Base output model with common fields for all tool responses.
    
    Following the June 18th 2025 MCP spec, outputs can include both
    traditional content blocks and structured content. This base class
    provides fields common to all tool outputs.
    
    The output includes three levels of metadata:
    1. Basic fields (session_id, execution_mode, model_used) for compatibility
    2. Request metadata (ephemeral, from FastMCP context)
    3. Session metadata (persistent, from CompanionSessionManager)
    """
    # === BASIC FIELDS (backward compatible) ===
    session_id: str = Field(
        description="Session ID for conversation continuity"
    )
    
    execution_mode: ExecutionMode = Field(
        description="Whether execution happened on client or server"
    )
    
    model_used: str = Field(
        description="The actual model that generated the content"
    )
    
    # === METADATA FIELDS ===
    request_metadata: Optional[RequestMetadata] = Field(
        default=None,
        description="Request-scoped metadata from FastMCP context"
    )
    
    session_metadata: Optional[SessionMetadata] = Field(
        default=None,
        description="Session-scoped metadata from CompanionSessionManager"
    )
    
    iteration_metadata: Optional[IterationMetadata] = Field(
        default=None,
        description="Current iteration metadata for convergence tracking"
    )
    
    # Legacy timestamp field for backward compatibility
    timestamp: Annotated[
        Optional[str],
        "ISO format timestamp of generation (use request_metadata.timestamp instead)"
    ] = None


# =====================================================================
# ERROR TYPES
# =====================================================================

class ErrorCode(str, Enum):
    """Standard error codes for MCP responses."""
    NO_DRAFT = "no_draft"
    NO_CRITIQUE = "no_critique"
    INVALID_SESSION = "invalid_session"
    POLLUTION_DETECTED = "pollution_detected"
    NONCE_MISMATCH = "nonce_mismatch"
    VALIDATION_ERROR = "validation_error"