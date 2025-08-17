"""
Phase Metrics Middleware - Simplified tracking of real metrics

This replaces the overly complex PhaseIntelligenceMiddleware with simple,
honest metrics tracking that actually works.
"""

import time
import logging
from datetime import datetime


from services.companion_manager import session_manager
from fastmcp.server.middleware import Middleware, MiddlewareContext


logger = logging.getLogger(__name__)


class PhaseMetricsMiddleware(Middleware):
    """
    Simple metrics tracking for the three-phase recursive reasoning cycle.
    
    Tracks REAL metrics:
    - Iteration counts
    - Phase timings
    - Similarity scores (when available)
    - Convergence detection
    
    Does NOT do:
    - Fake pattern matching
    - Hardcoded "intelligence"
    - Speculative suggestions
    """
    
    def __init__(self):
        """Initialize the metrics middleware."""
        self.logger = logger
        
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Track metrics for tool execution."""
        
        # Get context info
        ctx = context.fastmcp_context
        if not ctx:
            return await call_next(context)
            
        tool_name = context.message.name
        session_id = ctx.session_id
        
        # Skip non-phase tools
        if tool_name not in ["draft", "critique", "revise", "draft_complete", 
                            "critique_complete", "revise_complete"]:
            return await call_next(context)
        
        # Track timing
        start_time = time.time()
        
        try:
            # Execute the tool
            result = await call_next(context)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Update metrics after successful execution
            await self._update_metrics(tool_name, session_id, duration, context)
            
            return result
            
        except Exception as e:
            # Track failures
            await self._track_failure(tool_name, session_id, str(e))
            raise
    
    async def _update_metrics(self, tool_name: str, session_id: str, 
                             duration: float, context: MiddlewareContext):
        """Update metrics in persistent middleware state."""
        
        # Get middleware state from session
        middleware_state = session_manager.get_middleware_state(session_id)
        
        # Initialize metrics if needed
        if "metrics" not in middleware_state:
            middleware_state["metrics"] = {
                "total_requests": 0,
                "phase_counts": {},
                "average_durations": {},
                "last_similarity_score": None,
                "convergence_detected": False,
                "failures": []
            }
        
        metrics = middleware_state["metrics"]
        
        # Update basic metrics
        metrics["total_requests"] += 1
        
        # Track phase counts
        phase_name = tool_name.replace("_complete", "")
        if phase_name not in metrics["phase_counts"]:
            metrics["phase_counts"][phase_name] = 0
        metrics["phase_counts"][phase_name] += 1
        
        # Track average durations (simple moving average)
        if phase_name not in metrics["average_durations"]:
            metrics["average_durations"][phase_name] = duration
        else:
            # Simple exponential moving average
            alpha = 0.3  # Weight for new value
            metrics["average_durations"][phase_name] = (
                alpha * duration + (1 - alpha) * metrics["average_durations"][phase_name]
            )
        
        # Check for similarity score in run_log (if this was a revise)
        if phase_name == "revise":
            companion_type = context.message.arguments.get("companion_type", "generic")
            try:
                comp = session_manager.get_companion(session_id, companion_type)
                if comp.run_log:
                    last_slot = comp.run_log[-1]
                    similarity_score = last_slot.get("similarity_score")
                    
                    if similarity_score is not None:
                        metrics["last_similarity_score"] = similarity_score
                        
                        # Check for convergence
                        if similarity_score >= comp.similarity_threshold:
                            metrics["convergence_detected"] = True
                            self.logger.info(f"Convergence detected in session {session_id[:8]}: {similarity_score:.4f}")
            except Exception as e:
                self.logger.debug(f"Could not check similarity: {e}")
        
        # Save the updated metrics
        session_manager.set_middleware_state(session_id, "metrics", metrics)
        
        # Log summary
        self.logger.debug(
            f"Phase {phase_name} completed in {duration:.2f}s "
            f"(session {session_id[:8]}, "
            f"total requests: {metrics['total_requests']})"
        )
    
    async def _track_failure(self, tool_name: str, session_id: str, error: str):
        """Track tool failures."""
        
        middleware_state = session_manager.get_middleware_state(session_id)
        
        if "metrics" not in middleware_state:
            middleware_state["metrics"] = {
                "total_requests": 0,
                "phase_counts": {},
                "average_durations": {},
                "last_similarity_score": None,
                "convergence_detected": False,
                "failures": []
            }
        
        # Add failure record
        middleware_state["metrics"]["failures"].append({
            "tool": tool_name,
            "error": error[:200],  # Truncate long errors
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 10 failures
        if len(middleware_state["metrics"]["failures"]) > 10:
            middleware_state["metrics"]["failures"] = middleware_state["metrics"]["failures"][-10:]
        
        session_manager.set_middleware_state(session_id, "metrics", middleware_state["metrics"])
        
        self.logger.error(f"Tool {tool_name} failed in session {session_id[:8]}: {error}")