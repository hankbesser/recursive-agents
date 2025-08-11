# schema/inputs.py
"""
Input models for Recursive Agents MCP Server tools.

These Pydantic models define the input schemas for all MCP tools,
providing validation, type coercion, and automatic JSON schema
generation for the MCP protocol.
"""

from pydantic import Field, field_validator
from typing import Optional, Any, Dict
import re

# Import shared types from common
from .common import (
    SamplingConfig,
    BaseToolInput as CommonBaseToolInput
)

# =====================================================================
# BASE TOOL INPUT WITH VALIDATION
# =====================================================================

class BaseToolInput(CommonBaseToolInput):
    """
    Extended base input with session ID validation.
    
    We extend the common BaseToolInput here to add the session_id
    validator without circular imports.
    """
    
    @field_validator('session_id', mode='before')
    @classmethod
    def validate_session_id_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate session ID format if provided."""
        if v is None or v == "":
            return None
        
        # Ensure it's a string
        v = str(v).strip()
        if not v:
            return None
            
        # UUID v4 has specific pattern: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        # where y is one of [8, 9, a, b]
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        if not re.match(pattern, v, re.IGNORECASE):
            raise ValueError(f'Invalid session ID format. Expected UUID v4, got: {v}')
        return v.lower()  # Normalize to lowercase


# =====================================================================
# DRAFT PHASE INPUTS
# =====================================================================

class GenerateDraftInput(BaseToolInput):
    """
    Input schema for the draft generation tool.
    
    The draft tool always elicits the query from the user - either confirming
    a provided query or asking for one. It also elicits execution preference
    (client vs server) if not set. Creates or continues analysis in run_log.
    """
    query: str = Field(
        default="", 
        description="Initial query suggestion. Tool will always confirm with user before proceeding."
    )
    sampling: SamplingConfig = Field(
        default_factory=SamplingConfig,
        description="LLM sampling configuration. If use_client_sampling is None, tool will elicit preference."
    )
    
    @field_validator('query', mode='before')
    @classmethod
    def clean_query(cls, v: Any) -> str:
        """Convert to string and strip whitespace."""
        if v is None:
            return ""
        return str(v).strip()


class DraftCompleteInput(BaseToolInput):
    """
    Input schema for completing client-side draft generation.
    
    Called after client generates draft with their own model to
    sync state back to the server.
    """
    query: str = Field(
        ...,
        description="The original query that was answered"
    )
    draft: str = Field(
        ...,
        min_length=1,
        description="The generated draft content"
    )
    nonce: str = Field(
        ..., 
        description="Security token from draft request (prevents replay attacks)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Client model info (e.g., {'model': 'claude-3', 'variant': 'claude-3', 'temperature': 0.7})"
    )
    
    @field_validator('draft', mode='before')
    @classmethod
    def draft_not_empty(cls, v: Any) -> str:
        """Ensure draft contains meaningful content."""
        v = str(v).strip()
        if not v:
            raise ValueError('Draft cannot be empty')
        return v


# =====================================================================
# CRITIQUE PHASE INPUTS
# =====================================================================

class CritiqueDraftInput(BaseToolInput):
    """
    Input schema for the critique tool.
    
    REQUIRES an existing draft in run_log - will error if none exists.
    Always critiques the latest content (original draft or most recent revision)
    from the session state. Input parameters for query/draft are ignored.
    """
    query: str = Field(
        default="",
        description="Ignored. Tool uses query from run_log."
    )
    draft: str = Field(
        default="",
        description="Ignored. Tool uses latest content (draft or revision) from run_log."
    )
    sampling: SamplingConfig = Field(
        default_factory=SamplingConfig,
        description="LLM sampling configuration"
    )
    
    @field_validator('query', 'draft', mode='before')
    @classmethod
    def clean_fields(cls, v: Any) -> str:
        """Convert to string and strip whitespace."""
        if v is None:
            return ""
        return str(v).strip()


class CritiqueCompleteInput(BaseToolInput):
    """
    Input schema for completing client-side critique generation.
    
    Syncs client-generated critique back to server state.
    """
    query: str = Field(
        ...,
        description="The original query that was critiqued"
    )
    draft: str = Field(
        ...,
        description="The draft that was critiqued"
    )
    critique: str = Field(
        ...,
        min_length=1,
        description="The generated critique"
    )
    nonce: str = Field(
        ..., 
        description="Security token from critique request"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Client model info and generation metadata"
    )
    
    @field_validator('critique', mode='before')
    @classmethod
    def critique_not_empty(cls, v: Any) -> str:
        """Ensure critique contains meaningful content."""
        v = str(v).strip()
        if not v:
            raise ValueError('Critique cannot be empty')
        return v


# =====================================================================
# REVISE PHASE INPUTS  
# =====================================================================

class ReviseInput(BaseToolInput):
    """
    Input schema for the revision tool.
    
    REQUIRES both a draft AND critique to exist in run_log - will error if either
    is missing. Always uses the latest critique to revise the latest content.
    All input parameters for query/draft/critique are ignored.
    """
    query: str = Field(
        default="",
        description="Ignored. Tool uses query from run_log."
    )
    draft: str = Field(
        default="",
        description="Ignored. Tool uses latest content (draft or revision) from run_log."
    )
    critique: str = Field(
        default="",
        description="Ignored. Tool uses latest critique from run_log."
    )
    sampling: SamplingConfig = Field(
        default_factory=SamplingConfig,
        description="LLM sampling configuration"
    )
    
    @field_validator('query', 'draft', 'critique', mode='before')
    @classmethod
    def clean_fields(cls, v: Any) -> str:
        """Convert to string and strip whitespace."""
        if v is None:
            return ""
        return str(v).strip()


class ReviseCompleteInput(BaseToolInput):
    """
    Input schema for completing client-side revision generation.
    
    Final step in client-side execution, syncs revision to server.
    """
    query: str = Field(
        ...,
        description="The original query that was revised"
    )
    draft: str = Field(
        ...,
        description="The draft that was revised"
    )
    critique: str = Field(
        ...,
        description="The critique that guided revision"
    )
    revision: str = Field(
        ...,
        min_length=1,
        description="The generated revision"
    )
    nonce: str = Field(
        ..., 
        description="Security token from revise request"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Client model info and generation metadata"
    )
    
    @field_validator('revision', mode='before')
    @classmethod
    def revision_not_empty(cls, v: Any) -> str:
        """Ensure revision contains meaningful content."""
        v = str(v).strip()
        if not v:
            raise ValueError('Revision cannot be empty')
        return v
