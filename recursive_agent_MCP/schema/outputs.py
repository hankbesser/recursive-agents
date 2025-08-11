# schema/outputs.py
"""
Output models for Recursive Agents MCP Server tools.

Following the June 18th 2025 MCP spec, these models define structured
content that can be returned alongside traditional content blocks.
The structured content enables clients to deserialize responses back
to Python objects for programmatic use.
"""

from typing import Annotated, Optional, Literal, Dict, Any
from pydantic import BaseModel
from .common import (
    BaseToolOutput, 
    ExecutionMode,
    RequestMetadata,
    SessionMetadata, 
    IterationMetadata,
    Phase
)

# =====================================================================
# DRAFT PHASE OUTPUTS
# =====================================================================

class DraftServerOutput(BaseToolOutput):
    """
    Output from server-side draft generation.
    
    Current implementation returns: {"draft": str, "session_id": str}
    This schema includes additional fields for future enhancement.
    """
    draft: Annotated[str, "The generated draft content"]
    
    # TODO: Additional metadata to implement
    # query: Annotated[str, "The query that was answered"]
    # iteration_count: Annotated[int, "Current number of iterations in run_log"] = 0
    # variant: Annotated[str, "Model variant used (for tracking)"] = "server-default"


class DraftClientOutput(BaseModel):
    """
    Output from client-side draft generation request.
    
    When use_client_sampling=True, the server returns prompts and
    metadata for the client to execute with their own model.
    """
    # Prompts for client execution
    system: Annotated[str, "System prompt with injected protocol"]
    user: Annotated[str, "User prompt (the query)"]
    
    # Session management
    session_id: Annotated[str, "Session ID for continuity"]
    nonce: Annotated[str, "Security token to validate completion"]
    
    # Context info
    history_length: Annotated[int, "Number of messages in conversation history"]
    
    # Sampling config echoed back
    use_client_sampling: Literal[True] = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    
    # Any additional metadata
    metadata: Optional[Dict[str, Any]] = None


class DraftCompleteOutput(BaseModel):
    """
    Confirmation that client-side draft was logged successfully.
    
    Returned by tool_draft_complete after validating nonce and
    updating server state.
    """
    status: Literal["logged"] = "logged"
    session_id: Annotated[str, "Session ID for continuity"]


# =====================================================================
# CRITIQUE PHASE OUTPUTS
# =====================================================================

class CritiqueServerOutput(BaseToolOutput):
    """
    Output from server-side critique generation.
    
    Current implementation returns: {"critique": str, "session_id": str}
    This schema includes additional fields for future enhancement.
    """
    critique: Annotated[str, "The generated critique"]
    
    # TODO: Additional metadata to implement
    # draft_source: Annotated[str, "What was critiqued (e.g., 'original draft', 'revision #2')"]
    # critique_number: Annotated[int, "Which critique this is (1-based)"]
    # query: Annotated[str, "The original query"]


class CritiqueClientOutput(BaseModel):
    """
    Output from client-side critique generation request.
    
    When use_client_sampling=True, returns prompts for client execution.
    """
    # Prompts for client execution
    system: Annotated[str, "System prompt for critique generation"]
    user: Annotated[str, "User prompt with draft window and critique template"]
    
    # Session management
    session_id: Annotated[str, "Session ID for continuity"]
    nonce: Annotated[str, "Security token to validate completion"]
    
    # Sampling config
    use_client_sampling: Literal[True] = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    
    metadata: Optional[Dict[str, Any]] = None


class CritiqueCompleteOutput(BaseModel):
    """
    Confirmation that client-side critique was logged successfully.
    """
    status: Literal["logged"] = "logged"
    session_id: Annotated[str, "Session ID for continuity"]


# =====================================================================
# REVISE PHASE OUTPUTS
# =====================================================================

class ReviseServerOutput(BaseToolOutput):
    """
    Output from server-side revision generation.
    
    Current implementation returns: {"revision": str, "session_id": str}
    This schema includes additional fields for future enhancement.
    """
    revision: Annotated[str, "The generated revision"]
    
    # TODO: Additional metadata to implement
    # revision_number: Annotated[int, "Which revision this is (1-based)"]
    # based_on_critique: Annotated[int, "Which critique number guided this revision"]
    # draft_source: Annotated[str, "What was revised (e.g., 'original draft', 'revision #1')"]
    # query: Annotated[str, "The original query"]
    # is_final: Annotated[bool, "Hint that no more revisions expected"] = False


class ReviseClientOutput(BaseModel):
    """
    Output from client-side revision generation request.
    
    When use_client_sampling=True, returns prompts for client execution.
    """
    # Prompts for client execution
    system: Annotated[str, "System prompt for revision generation"]
    user: Annotated[str, "User prompt with draft, critique, and revision template"]
    
    # Session management
    session_id: Annotated[str, "Session ID for continuity"]
    nonce: Annotated[str, "Security token to validate completion"]
    
    # Sampling config
    use_client_sampling: Literal[True] = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    
    metadata: Optional[Dict[str, Any]] = None


class ReviseCompleteOutput(BaseModel):
    """
    Confirmation that client-side revision was logged successfully.
    """
    status: Literal["logged"] = "logged"
    session_id: Annotated[str, "Session ID for continuity"]


# =====================================================================
# UNIFIED OUTPUT TYPES (for tool return annotations)
# =====================================================================

# Union types that tools can use for return annotations
DraftOutput = DraftServerOutput | DraftClientOutput
CritiqueOutput = CritiqueServerOutput | CritiqueClientOutput  
ReviseOutput = ReviseServerOutput | ReviseClientOutput


# =====================================================================
# ERROR OUTPUTS (Optional - FastMCP handles errors automatically)
# =====================================================================

class ErrorOutput(BaseModel):
    """
    Structured error response (if needed for custom error handling).
    
    Note: FastMCP automatically converts exceptions to MCP error responses,
    so this is only needed if you want structured error data.
    """
    error_code: str
    error_message: str
    session_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None