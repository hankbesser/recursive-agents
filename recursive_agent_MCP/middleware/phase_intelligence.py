# recursive_agent_MCP/middleware/phase_intelligence.py
"""
Phase Intelligence Middleware for the three-phase reasoning system.

This middleware adds intelligence on top of validation, tracking phase progression,
suggesting next actions, and providing insights into the iteration process.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any #, List
from mcp import McpError
from mcp.types import ErrorData
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from services.companion_manager import session_manager
from schema.common import ExecutionMode


class PhaseIntelligenceMiddleware(Middleware):
    """Orchestrates and provides intelligence for the three-phase reasoning process.
    
    Goes beyond validation to:
    - Track phase progression and timing
    - Analyze iteration patterns
    - Suggest next actions
    - Detect convergence signals
    - Provide iteration quality metrics
    """
    
    def __init__(
        self,
        logger: logging.Logger | None = None,
        track_metrics: bool = True,
        suggest_actions: bool = True,
        convergence_detection: bool = True,
    ):
        self.logger = logger or logging.getLogger("fastmcp.phase_intelligence")
        self.track_metrics = track_metrics
        self.suggest_actions = suggest_actions
        self.convergence_detection = convergence_detection
        
        # Cross-session metrics for learning
        self.global_metrics = {
            "avg_iterations_by_type": {},  # companion_type -> avg iterations
            "phase_timings": {},  # phase -> avg duration
            "convergence_patterns": []
        }
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        """Orchestrate phase-based tool calls with intelligence."""
        tool_name = context.message.name
        
        # Process both main tools and completion tools
        main_tools = ["draft", "critique", "revise"]
        completion_tools = ["draft_complete", "critique_complete", "revise_complete"]
        
        if tool_name not in main_tools + completion_tools:
            return await call_next(context)
        
        ctx = context.fastmcp_context
        if not ctx:
            return await call_next(context)
        
        try:
            # For main tools: full lifecycle
            if tool_name in main_tools:
                # 1. Load and analyze current state
                state_analysis = await self._analyze_iteration_state(context, ctx)
                
                # 2. Set pre-execution context
                await self._set_phase_context(tool_name, state_analysis, ctx)
                
                # 3. Execute with timing
                start_time = time.perf_counter()
                result = await call_next(context)
                duration = time.perf_counter() - start_time
                
                # 4. Post-execution tracking and intelligence
                if self.track_metrics:
                    await self._track_phase_metrics(tool_name, duration, state_analysis, ctx)
                
                if self.suggest_actions:
                    await self._generate_intelligent_suggestions(tool_name, state_analysis, ctx)
                
                if self.convergence_detection:
                    await self._detect_convergence_signals(state_analysis, ctx)
                
                # 5. Fire completion hook for server-side execution
                if hasattr(result, 'execution_mode') and result.execution_mode == ExecutionMode.SERVER:
                    await self._on_phase_complete(tool_name, result, state_analysis, ctx, duration)
                
                return result
            
            # For completion tools: just fire the hook
            else:
                # Execute the completion tool
                result = await call_next(context)
                
                # Extract the phase name (e.g., "draft_complete" -> "draft")
                phase_name = tool_name.replace("_complete", "")
                
                # Get current state for the completion
                state_analysis = await self._analyze_iteration_state(context, ctx)
                
                # Fire completion hook for client-side execution
                # Note: We don't have exact duration for client execution
                await self._on_phase_complete(phase_name, result, state_analysis, ctx, None)
                
                return result
            
        except McpError:
            raise
        except Exception as e:
            self.logger.error(f"Phase intelligence error in {tool_name}: {e}")
            raise McpError(
                ErrorData(code=-32603, message=f"Phase orchestration error: {str(e)}")
            )
    
    async def _analyze_iteration_state(self, context: MiddlewareContext, ctx) -> Dict[str, Any]:
        """Deeply analyze the current iteration state."""
        # Get companion and current slot
        session_id = ctx.session_id
        companion_type = context.message.arguments.get("companion_type", "generic")
        # Note: We don't pass sampling_config here since middleware is just analyzing state
        # The actual tools will create/update companion with proper sampling_config
        comp = session_manager.get_companion(session_id, companion_type)
        
        current_slot = comp.run_log[-1] if comp.run_log else None
        
        # Analyze phase position from array lengths
        if not current_slot:
            phase_position = "initial"
            iteration_number = 0
            current_phase_in_cycle = "draft"
        else:
            critiques = current_slot.get("critique", [])
            revisions = current_slot.get("revision", [])
            
            # Determine where we are in the cycle
            if len(critiques) == len(revisions):
                # Equal means we can critique again or draft new
                current_phase_in_cycle = "critique" if current_slot.get("draft") else "draft"
                iteration_number = len(critiques)
            elif len(critiques) > len(revisions):
                # More critiques than revisions means we need to revise
                current_phase_in_cycle = "revise"
                iteration_number = len(revisions)
            else:
                # This shouldn't happen with proper validation
                current_phase_in_cycle = "unknown"
                iteration_number = 0
        
        # Calculate total iterations across all slots
        total_iterations = sum(
            max(len(slot.get("critique", [])), len(slot.get("revision", [])))
            for slot in comp.run_log
        )
        
        return {
            "session_id": session_id,
            "companion_type": companion_type,
            "current_slot": current_slot,
            "phase_position": phase_position,
            "current_phase_in_cycle": current_phase_in_cycle,
            "iteration_number": iteration_number,
            "total_iterations": total_iterations,
            "slot_count": len(comp.run_log),
            "has_history": bool(comp.history),
            "query": current_slot.get("query") if current_slot else None
        }
    
    async def _set_phase_context(self, tool_name: str, state_analysis: Dict[str, Any], ctx):
        """Set rich context for the current phase."""
        # Initialize or update phase tracking
        phase_tracking = ctx.get_state("phase_tracking") or {}
        
        # Update with current phase info
        phase_tracking.update({
            "current_tool": tool_name,
            "iteration_number": state_analysis["iteration_number"],
            "total_iterations": state_analysis["total_iterations"],
            "phase_position": state_analysis["phase_position"],
            "timestamp": datetime.now().isoformat()
        })
        
        # Track phase sequence
        if "phase_sequence" not in phase_tracking:
            phase_tracking["phase_sequence"] = []
        phase_tracking["phase_sequence"].append({
            "phase": tool_name,
            "iteration": state_analysis["iteration_number"],
            "timestamp": datetime.now().isoformat()
        })
        
        ctx.set_state("phase_tracking", phase_tracking)
        
        # Log intelligence
        self.logger.info(
            f"Phase: {tool_name} | "
            f"Iteration: {state_analysis['iteration_number']} | "
            f"Total: {state_analysis['total_iterations']} | "
            f"Session: {state_analysis['session_id'][:8]}"
        )
    
    async def _track_phase_metrics(self, tool_name: str, duration: float, state_analysis: Dict[str, Any], ctx):
        """Track detailed metrics for learning."""
        # Update phase tracking with timing
        phase_tracking = ctx.get_state("phase_tracking", {})
        
        if "phase_timings" not in phase_tracking:
            phase_tracking["phase_timings"] = {}
        
        # Special handling for draft - it's always iteration 0 in phase_timings
        if tool_name == "draft":
            phase_key = f"{tool_name}_0"
        else:
            phase_key = f"{tool_name}_{state_analysis['iteration_number']}"
        phase_tracking["phase_timings"][phase_key] = duration
        
        # Calculate cumulative time
        total_time = sum(phase_tracking["phase_timings"].values())
        phase_tracking["total_duration"] = total_time
        
        ctx.set_state("phase_tracking", phase_tracking)
        
        # Update global metrics
        companion_type = state_analysis["companion_type"]
        if companion_type not in self.global_metrics["avg_iterations_by_type"]:
            self.global_metrics["avg_iterations_by_type"][companion_type] = []
        
        # This will be updated when iteration completes
        self.logger.debug(f"Phase {tool_name} completed in {duration:.2f}s")
    
    async def _generate_intelligent_suggestions(self, completed_phase: str, state_analysis: Dict[str, Any], ctx):
        """Generate context-aware suggestions based on iteration state."""
        suggestions = {}
        
        # Get phase tracking for history
        phase_tracking = ctx.get_state("phase_tracking", {})
        iteration_num = state_analysis["iteration_number"]
        
        if completed_phase == "draft":
            suggestions["next_action"] = "critique"
            suggestions["message"] = "Draft complete. Ready for critique phase to identify improvements."
            suggestions["confidence"] = "high"
            
        elif completed_phase == "critique":
            # Check if we have critiques without revisions
            if state_analysis["current_slot"]:
                critiques = state_analysis["current_slot"].get("critique", [])
                revisions = state_analysis["current_slot"].get("revision", [])
                
                if len(critiques) > len(revisions):
                    suggestions["next_action"] = "revise"
                    suggestions["message"] = "Critique complete. Ready to implement improvements."
                    suggestions["confidence"] = "high"
                else:
                    # Even critiques/revisions - can go either way
                    suggestions["next_action"] = "revise_or_finalize"
                    suggestions["message"] = f"After {len(critiques)} iterations, you can revise again or finalize."
                    suggestions["confidence"] = "medium"
                    
        elif completed_phase == "revise":
            # Analyze iteration patterns
            if iteration_num >= 3:
                suggestions["next_action"] = "consider_finalizing"
                suggestions["message"] = (
                    f"Completed {iteration_num} iterations. "
                    "Improvements are likely converging. Consider finalizing."
                )
                suggestions["confidence"] = "high"
                suggestions["rationale"] = "Diminishing returns typically occur after 3 iterations"
            else:
                suggestions["next_action"] = "critique"
                suggestions["message"] = "Revision complete. You can critique again for further refinement."
                suggestions["confidence"] = "medium"
        
        # Add iteration context
        suggestions["iteration_context"] = {
            "current_iteration": iteration_num,
            "total_time": phase_tracking.get("total_duration", 0),
            "phase_count": len(phase_tracking.get("phase_sequence", []))
        }
        
        ctx.set_state("suggestions", suggestions)
        
        # Log suggestion
        self.logger.info(f"Suggestion: {suggestions.get('message', 'No suggestion')}")
    
    async def _detect_convergence_signals(self, state_analysis: Dict[str, Any], ctx):
        """Detect signals that iteration is converging."""
        convergence_signals = []
        
        if state_analysis["current_slot"]:
            critiques = state_analysis["current_slot"].get("critique", [])
            revisions = state_analysis["current_slot"].get("revision", [])
            
            # Signal 1: High iteration count
            if len(critiques) >= 3:
                convergence_signals.append({
                    "type": "iteration_count",
                    "strength": "strong",
                    "message": f"{len(critiques)} iterations completed"
                })
            
            # Signal 2: Critique patterns (would need to analyze critique content)
            # This is where we could check for phrases like "minor improvements"
            # or "minimal changes" in the critique text
            
            # Signal 3: Time-based (long iterations might indicate difficulty)
            phase_tracking = ctx.get_state("phase_tracking", {})
            total_duration = phase_tracking.get("total_duration", 0)
            if total_duration > 300:  # 5 minutes
                convergence_signals.append({
                    "type": "duration",
                    "strength": "medium",
                    "message": f"Iteration running for {total_duration:.1f}s"
                })
        
        if convergence_signals:
            ctx.set_state("convergence_signals", convergence_signals)
            self.logger.info(f"Convergence signals detected: {len(convergence_signals)}")
    
    async def _on_phase_complete(
        self, 
        phase: str, 
        result: Any, 
        state_analysis: Dict[str, Any], 
        ctx, 
        duration: Optional[float]
    ):
        """
        Phase completion hook - fires after successful phase execution.
        
        This is where we:
        1. Capture what actually happened
        2. Update global learning metrics
        3. Extract patterns for future predictions
        4. Prepare context for next phase
        """
        self.logger.info(f"Phase complete: {phase} for session {state_analysis['session_id'][:8]}")
        
        # Extract the actual content from result
        content = None
        if hasattr(result, 'draft'):
            content = result.draft
        elif hasattr(result, 'critique'):
            content = result.critique
        elif hasattr(result, 'revision'):
            content = result.revision
        elif hasattr(result, 'status') and result.status == "logged":
            # Completion tool result - content is in the companion's run_log
            companion_type = state_analysis['companion_type']
            comp = session_manager.get_companion(
                state_analysis['session_id'], 
                companion_type
            )
            if comp.run_log:
                current_slot = comp.run_log[-1]
                if phase == "draft":
                    content = current_slot.get('draft')
                elif phase == "critique":
                    critiques = current_slot.get('critique', [])
                    content = critiques[-1] if critiques else None
                elif phase == "revise":
                    revisions = current_slot.get('revision', [])
                    content = revisions[-1] if revisions else None
        
        if not content:
            self.logger.warning(f"No content found for {phase} completion")
            return
        
        # Update global metrics
        await self._update_global_metrics_on_completion(
            phase, state_analysis, content, duration
        )
        
        # Extract and store patterns
        await self._extract_completion_patterns(
            phase, content, state_analysis, ctx
        )
        
        # Prepare context for next phase
        await self._prepare_next_phase_context(
            phase, content, state_analysis, ctx
        )
        
        # Check for convergence completion
        if phase == "revise":
            await self._check_iteration_completion(state_analysis, ctx)
    
    async def _update_global_metrics_on_completion(
        self, 
        phase: str, 
        state_analysis: Dict[str, Any], 
        content: str, 
        duration: Optional[float]
    ):
        """Update global metrics with actual data from completed phase."""
        companion_type = state_analysis['companion_type']
        
        # Track phase timings
        if duration is not None:
            phase_key = f"{phase}_timings"
            if phase_key not in self.global_metrics:
                self.global_metrics[phase_key] = []
            self.global_metrics[phase_key].append(duration)
            
            # Keep only last 100 for memory efficiency
            if len(self.global_metrics[phase_key]) > 100:
                self.global_metrics[phase_key] = self.global_metrics[phase_key][-100:]
        
        # Track content characteristics
        content_metrics = {
            'length': len(content),
            'phase': phase,
            'companion_type': companion_type,
            'iteration': state_analysis['iteration_number']
        }
        
        if 'content_patterns' not in self.global_metrics:
            self.global_metrics['content_patterns'] = []
        self.global_metrics['content_patterns'].append(content_metrics)
        
        # For revisions, check if this completes an iteration
        if phase == "revise":
            current_slot = state_analysis.get('current_slot')
            if current_slot:
                critiques = len(current_slot.get('critique', []))
                revisions = len(current_slot.get('revision', []))
                
                # If arrays are now balanced, iteration is complete
                if critiques == revisions:
                    if companion_type not in self.global_metrics['avg_iterations_by_type']:
                        self.global_metrics['avg_iterations_by_type'][companion_type] = []
                    
                    self.global_metrics['avg_iterations_by_type'][companion_type].append(revisions)
                    
                    # Calculate running average
                    iterations_list = self.global_metrics['avg_iterations_by_type'][companion_type]
                    avg = sum(iterations_list) / len(iterations_list)
                    
                    self.logger.info(
                        f"{companion_type} average iterations: {avg:.1f} "
                        f"(based on {len(iterations_list)} sessions)"
                    )
    
    async def _extract_completion_patterns(
        self, 
        phase: str, 
        content: str, 
        state_analysis: Dict[str, Any], 
        ctx
    ):
        """Extract patterns from completed phase for learning."""
        # Simple pattern extraction based on phase
        patterns = {}
        
        if phase == "critique":
            # Look for common critique patterns
            has_security = any(term in content.lower() for term in ['security', 'validation', 'sanitize'])
            has_performance = any(term in content.lower() for term in ['performance', 'optimize', 'efficient'])
            has_error_handling = any(term in content.lower() for term in ['error', 'exception', 'try', 'catch'])
            
            patterns['focus_areas'] = []
            if has_security:
                patterns['focus_areas'].append('security')
            if has_performance:
                patterns['focus_areas'].append('performance')
            if has_error_handling:
                patterns['focus_areas'].append('error_handling')
            
            # Store for revision to reference
            ctx.set_state('critique_patterns', patterns)
            
        elif phase == "revise":
            # Check if revision addressed critique patterns
            critique_patterns = ctx.get_state('critique_patterns')
            if critique_patterns and critique_patterns.get('focus_areas'):
                addressed = []
                for area in critique_patterns['focus_areas']:
                    if area in content.lower():
                        addressed.append(area)
                
                patterns['addressed_areas'] = addressed
                patterns['coverage'] = len(addressed) / len(critique_patterns['focus_areas']) if critique_patterns['focus_areas'] else 0
                
                self.logger.info(f"Revision addressed {patterns['coverage']:.0%} of critique focus areas")
        
        # Add to convergence patterns
        if patterns:
            pattern_record = {
                'phase': phase,
                'companion_type': state_analysis['companion_type'],
                'iteration': state_analysis['iteration_number'],
                'patterns': patterns,
                'timestamp': datetime.now().isoformat()
            }
            self.global_metrics['convergence_patterns'].append(pattern_record)
            
            # Keep only last 50 patterns
            if len(self.global_metrics['convergence_patterns']) > 50:
                self.global_metrics['convergence_patterns'] = self.global_metrics['convergence_patterns'][-50:]
    
    async def _prepare_next_phase_context(
        self, 
        completed_phase: str, 
        content: str, 
        state_analysis: Dict[str, Any], 
        ctx
    ):
        """Prepare context for the next phase based on what just completed."""
        # Create a summary of what just happened
        completion_summary = {
            'completed_phase': completed_phase,
            'content_length': len(content),
            'iteration': state_analysis['iteration_number'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Add phase-specific context
        if completed_phase == "draft":
            completion_summary['next_phase'] = 'critique'
            completion_summary['context'] = 'Initial draft established, ready for analysis'
            
        elif completed_phase == "critique":
            completion_summary['next_phase'] = 'revise'
            # Extract key critique points (first 200 chars)
            completion_summary['critique_preview'] = content[:200] + "..." if len(content) > 200 else content
            completion_summary['context'] = 'Critique identified improvements, ready for revision'
            
        elif completed_phase == "revise":
            # Check if we should continue or finalize
            iterations = state_analysis['iteration_number']
            avg_iterations = self._get_average_iterations(state_analysis['companion_type'])
            
            if iterations >= avg_iterations:
                completion_summary['next_phase'] = 'consider_finalize'
                completion_summary['context'] = f'Reached average iterations ({avg_iterations:.1f})'
            else:
                completion_summary['next_phase'] = 'critique'
                completion_summary['context'] = 'Revision complete, can critique again'
        
        # Store in context for next phase
        ctx.set_state('previous_phase_summary', completion_summary)
    
    async def _check_iteration_completion(self, state_analysis: Dict[str, Any], ctx):
        """Check if an iteration is complete and extract learnings."""
        current_slot = state_analysis.get('current_slot')
        if not current_slot:
            return
        
        critiques = len(current_slot.get('critique', []))
        revisions = len(current_slot.get('revision', []))
        
        # Iteration is complete when arrays are balanced
        if critiques == revisions and critiques > 0:
            # Extract similarity score if available
            # Note: This would need to be exposed by BaseCompanion
            similarity_score = None  # TODO: Get from companion
            
            iteration_summary = {
                'companion_type': state_analysis['companion_type'],
                'total_iterations': critiques,
                'query': current_slot.get('query', '')[:50],  # First 50 chars
                'similarity_score': similarity_score,
                'completed_at': datetime.now().isoformat()
            }
            
            self.logger.info(
                f"Iteration complete: {state_analysis['companion_type']} "
                f"completed {critiques} cycles for query '{iteration_summary['query']}...'"
            )
            
            # Fire a special event for iteration completion
            ctx.set_state('iteration_complete', iteration_summary)
    
    def _get_average_iterations(self, companion_type: str) -> float:
        """Get average iterations for a companion type."""
        if companion_type in self.global_metrics['avg_iterations_by_type']:
            iterations_list = self.global_metrics['avg_iterations_by_type'][companion_type]
            if iterations_list:
                return sum(iterations_list) / len(iterations_list)
        
        # Default averages if no data yet
        defaults = {
            'marketing': 2.0,
            'bug_triage': 3.0,
            'strategy': 2.5,
            'generic': 3.0
        }
        return defaults.get(companion_type, 3.0)
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all sessions."""
        return self.global_metrics.copy()