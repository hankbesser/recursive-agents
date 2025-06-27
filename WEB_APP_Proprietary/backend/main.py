# backend/main.py
"""
FastAPI backend for Recursive Companion streaming interface.

Features:
- Server-Sent Events for real-time streaming
- WebSocket support (optional)
- Template viewing endpoints
- Configuration management
"""
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory (recursive-companion root) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import your companions
from recursive_companion.base import (
    GenericCompanion,
    MarketingCompanion,
    BugTriageCompanion,
    StrategyCompanion
)

app = FastAPI(title="Recursive Companion API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Companion mapping
COMPANION_MAP = {
    "generic": GenericCompanion,
    "marketing": MarketingCompanion,
    "bug_triage": BugTriageCompanion,
    "strategy": StrategyCompanion
}

# Request/Response models
class AnalysisRequest(BaseModel):
    query: str
    companion_type: str = "generic"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_loops: int = 3
    similarity_threshold: float = 0.98

class TemplateInfo(BaseModel):
    name: str
    content: str
    
# First, add this to your BaseCompanion in chains.py:
async def loop_streaming(self, user_input: str):
    """
    Async generator version that yields progress updates for streaming.
    
    Yields dicts with:
        - phase: "initial_draft" | "critique" | "revision" | "complete"
        - content: The text content
        - iteration: Current loop number
        - similarity: Similarity score (if applicable)
        - is_final: Boolean indicating completion
    """
    self.run_log.clear()
    
    # 1. Initial draft (using sync method for now)
    draft = self.init_chain.invoke(
        {"user_input": user_input, "history": self.history}
    ).content
    
    yield {
        "phase": "initial_draft",
        "content": draft,
        "iteration": 0,
        "similarity": None,
        "is_final": False
    }
    
    prev = None
    prev_emb = None
    
    # 2. Critique/revision cycles
    for i in range(1, self.max_loops + 1):
        # Critique
        critique = self.crit_chain.invoke(
            {"user_input": user_input, "draft": draft}
        ).content
        
        yield {
            "phase": "critique",
            "content": critique,
            "iteration": i,
            "similarity": None,
            "is_final": False
        }
        
        # Early exit check
        if any(p in critique.lower() for p in ("no further improvements", "minimal revisions")):
            self.run_log.append({"draft": draft, "critique": critique, "revision": draft})
            yield {
                "phase": "complete",
                "content": draft,
                "iteration": i,
                "similarity": None,
                "is_final": True,
                "reason": "no_improvements"
            }
            break
        
        # Revision
        revised = self.crit_chain.invoke(
            {"user_input": user_input, "draft": draft, "critique": critique}
        ).content
        
        # Compute similarity
        sim = None
        if prev is not None:
            if prev_emb is None:
                prev_emb = self._emb.embed_query(prev)
            cur_emb = self._emb.embed_query(revised)
            from core.chains import cosine_from_embeddings
            sim = cosine_from_embeddings(prev_emb, cur_emb)
        
        yield {
            "phase": "revision", 
            "content": revised,
            "iteration": i,
            "similarity": sim,
            "is_final": False
        }
        
        # Check convergence
        if sim is not None and sim >= self.similarity_threshold:
            self.run_log.append({
                "draft": draft,
                "critique": critique,
                "revision": revised
            })
            yield {
                "phase": "complete",
                "content": revised,
                "iteration": i,
                "similarity": sim,
                "is_final": True,
                "reason": "converged"
            }
            draft = revised
            break
        
        # Continue loop
        self.run_log.append({"draft": draft, "critique": critique, "revision": revised})
        prev = draft
        if 'cur_emb' in locals():
            prev_emb = cur_emb
        draft = revised
    
    else:
        # Max loops reached
        yield {
            "phase": "complete",
            "content": draft,
            "iteration": self.max_loops,
            "similarity": None,
            "is_final": True,
            "reason": "max_loops"
        }
    
    # Update history
    self.history.extend([HumanMessage(user_input), AIMessage(draft)])
    if self.clear_history:
        self.history.clear()

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Recursive Companion API", "version": "1.0"}

@app.get("/analyze/stream")  # <-- Change this to GET
async def analyze_stream(
    query: str,
    companion_type: str = "generic",
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_loops: int = 3,
    similarity_threshold: float = 0.98
):
    """Stream analysis results using Server-Sent Events."""
    
    # Validate companion type
    if companion_type not in COMPANION_MAP:
        raise HTTPException(400, f"Invalid companion type: {companion_type}")
    
    # Create companion instance
    companion_class = COMPANION_MAP[companion_type]
    companion = companion_class(
        llm=model,
        temperature=temperature,
        max_loops=max_loops,
        similarity_threshold=similarity_threshold,
        clear_history=True
    )
    
    async def generate():
        """Generate SSE events."""
        try:
            async for update in companion.loop_streaming(query):  # <-- This will call the method from BaseCompanion
                # Format as Server-Sent Event
                event_data = json.dumps(update)
                yield f"data: {event_data}\n\n"
                
                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)
                
        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """Non-streaming analysis endpoint."""
    
    if request.companion_type not in COMPANION_MAP:
        raise HTTPException(400, f"Invalid companion type: {request.companion_type}")
    
    companion_class = COMPANION_MAP[request.companion_type]
    companion = companion_class(
        llm=request.model,
        temperature=request.temperature,
        max_loops=request.max_loops,
        similarity_threshold=request.similarity_threshold,
        return_transcript=True,
        clear_history=True
    )
    
    final_answer, run_log = companion.loop(request.query)
    
    return {
        "final_answer": final_answer,
        "run_log": run_log,
        "iterations": len(run_log),
        "companion_type": request.companion_type
    }

@app.get("/companions")
async def list_companions():
    """List available companion types."""
    return {
        "companions": list(COMPANION_MAP.keys()),
        "details": {
            "generic": "Domain-agnostic analysis",
            "marketing": "Growth and audience insights", 
            "bug_triage": "Technical root cause analysis",
            "strategy": "Cross-functional synthesis"
        }
    }

@app.get("/templates/{companion_type}")
async def get_templates(companion_type: str):
    """Get templates for a specific companion type."""
    
    template_dir = Path(__file__).parent.parent / "templates"
    
    # Map companion types to their template files
    template_mapping = {
        "generic": ["generic_initial_sys", "generic_critique_sys", "generic_revision_sys"],
        "marketing": ["marketing_initial_sys", "generic_critique_sys", "generic_revision_sys"],
        "bug_triage": ["bug_triage_initial_sys", "generic_critique_sys", "generic_revision_sys"],
        "strategy": ["strategy_initial_sys", "generic_critique_sys", "generic_revision_sys"]
    }
    
    if companion_type not in template_mapping:
        raise HTTPException(404, f"Templates not found for: {companion_type}")
    
    templates = {}
    for template_name in template_mapping[companion_type]:
        template_path = template_dir / f"{template_name}.txt"
        if template_path.exists():
            templates[template_name] = template_path.read_text()
    
    # Also include protocol context
    protocol_path = template_dir / "protocol_context.txt"
    if protocol_path.exists():
        templates["protocol_context"] = protocol_path.read_text()
    
    return templates

@app.get("/models")
async def list_models():
    """List available models."""
    return {
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4 Optimized Mini", "default": True},
            {"id": "gpt-4o", "name": "GPT-4 Optimized"},
            {"id": "gpt-4", "name": "GPT-4"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
