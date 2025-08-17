"""
Session Metrics Resources
========================

Exposes metrics tracked by PhaseMetricsMiddleware and aggregates session data.

Important architectural notes:
- PhaseMetricsMiddleware only tracks phase tools (draft/critique/revise)
- Metrics are stored in session's middleware_state["metrics"]
- These resources READ existing data, they don't capture new metrics
- True session-wide metrics would require middleware that tracks ALL tools

Data sources:
1. middleware_state["metrics"] - Phase execution metrics from PhaseMetricsMiddleware
2. session_data timestamps - created_at, last_accessed from CompanionSessionManager
3. companion.run_log - Iteration counts and similarity scores
"""

from typing import Dict, Any
from datetime import datetime
from services.companion_manager import session_manager


async def resource_session_phase_metrics(session_id: str) -> Dict[str, Any]:
    """
    Get phase execution metrics for a specific session.
    
    URI: resource://sessions/{session_id}/phase_metrics
    
    Returns what PhaseMetricsMiddleware tracked for this session:
    - Phase execution counts and timings
    - Convergence detection
    - Recent failures
    
    Note: This only includes phase tools, not all session activity.
    """
    
    session_data = session_manager.sessions.get(session_id)
    if not session_data:
        return {
            "error": "Session not found",
            "session_id": session_id
        }
    
    # Get metrics from middleware_state (where PhaseMetricsMiddleware stores them)
    middleware_state = session_data.get("middleware_state", {})
    metrics = middleware_state.get("metrics", {})
    
    if not metrics:
        return {
            "session_id": session_id,
            "message": "No phase metrics collected yet",
            "hint": "Phase metrics are only tracked after calling draft, critique, or revise tools"
        }
    
    # Return exactly what PhaseMetricsMiddleware tracked
    return {
        "session_id": session_id,
        "phase_metrics": {
            "total_phase_requests": metrics.get("total_requests", 0),
            "phase_counts": metrics.get("phase_counts", {}),
            "average_phase_durations_seconds": metrics.get("average_durations", {}),
            "last_similarity_score": metrics.get("last_similarity_score"),
            "convergence_detected": metrics.get("convergence_detected", False),
            "recent_failures": metrics.get("failures", [])
        },
        "note": "These metrics only track phase tools (draft/critique/revise), not all session activity"
    }


async def resource_session_timing_metrics(session_id: str) -> Dict[str, Any]:
    """
    Get timing and performance metrics for a session.
    
    URI: resource://sessions/{session_id}/timing_metrics
    
    Returns ONLY timing-related data:
    - Phase execution timing from middleware_state
    - Session age and idle time
    - NO companion content analysis (use session_resources for that)
    """
    
    session_data = session_manager.sessions.get(session_id)
    if not session_data:
        return {
            "error": "Session not found",
            "session_id": session_id
        }
    
    # Calculate session-level timing
    created_at = session_data.get("created_at", datetime.now())
    last_accessed = session_data.get("last_accessed", datetime.now())
    session_age_seconds = (datetime.now() - created_at).total_seconds()
    idle_seconds = (datetime.now() - last_accessed).total_seconds()
    
    # Get phase metrics from middleware
    middleware_state = session_data.get("middleware_state", {})
    phase_metrics = middleware_state.get("metrics", {})
    
    
    # Return ONLY timing-related metrics
    return {
        "session_id": session_id,
        
        "session_timing": {
            "created_at": created_at.isoformat(),
            "last_accessed": last_accessed.isoformat(),
            "session_age_seconds": session_age_seconds,
            "idle_seconds": idle_seconds,
            "is_active": idle_seconds < 1800  # Active if used in last 30 min
        },
        
        "phase_timing": {
            "total_phase_calls": phase_metrics.get("total_requests", 0),
            "phase_counts": phase_metrics.get("phase_counts", {}),
            "average_durations_seconds": phase_metrics.get("average_durations", {}),
        },
        
        "convergence": {
            "detected": phase_metrics.get("convergence_detected", False),
            "last_similarity_score": phase_metrics.get("last_similarity_score")
        },
        
        "failures": phase_metrics.get("failures", []) if phase_metrics.get("failures") else [],
        
        "note": "For companion state and iteration counts, use resource://sessions/{session_id}/{companion_type}/phase"
    }


async def resource_all_sessions_timing_aggregate() -> Dict[str, Any]:
    """
    Aggregate timing metrics across all active sessions.
    
    URI: resource://metrics/all_sessions_timing
    
    Provides system-wide view of phase execution timing.
    Focus: ONLY middleware timing metrics, no companion analysis.
    """
    
    total_sessions = 0
    sessions_with_metrics = 0
    total_phase_requests = 0
    phase_counts_aggregate = {}
    duration_sums = {}
    duration_counts = {}
    convergence_count = 0
    
    # Scan all sessions for timing metrics only
    for session_id, session_data in session_manager.sessions.items():
        total_sessions += 1
        
        # Get phase metrics from middleware
        middleware_state = session_data.get("middleware_state", {})
        metrics = middleware_state.get("metrics", {})
        
        if metrics:
            sessions_with_metrics += 1
            total_phase_requests += metrics.get("total_requests", 0)
            
            # Aggregate phase counts
            for phase, count in metrics.get("phase_counts", {}).items():
                phase_counts_aggregate[phase] = phase_counts_aggregate.get(phase, 0) + count
            
            # Collect durations for averaging
            for phase, duration in metrics.get("average_durations", {}).items():
                if phase not in duration_sums:
                    duration_sums[phase] = 0
                    duration_counts[phase] = 0
                duration_sums[phase] += duration
                duration_counts[phase] += 1
            
            # Count convergence
            if metrics.get("convergence_detected"):
                convergence_count += 1
    
    # Calculate averages
    average_durations_global = {}
    for phase in duration_sums:
        if duration_counts[phase] > 0:
            average_durations_global[phase] = duration_sums[phase] / duration_counts[phase]
    
    # Calculate rates
    convergence_rate = convergence_count / sessions_with_metrics if sessions_with_metrics > 0 else 0
    metrics_coverage = sessions_with_metrics / total_sessions if total_sessions > 0 else 0
    
    return {
        "summary": {
            "total_sessions": total_sessions,
            "sessions_with_metrics": sessions_with_metrics,
            "metrics_coverage": metrics_coverage
        },
        
        "phase_timing_aggregate": {
            "total_phase_requests": total_phase_requests,
            "phase_counts": phase_counts_aggregate,
            "average_durations_seconds": average_durations_global
        },
        
        "convergence": {
            "sessions_with_convergence": convergence_count,
            "convergence_rate": convergence_rate
        },
        
        "timestamp": datetime.now().isoformat()
    }


async def resource_companion_type_timing(companion_type: str) -> Dict[str, Any]:
    """
    Analyze timing performance for a specific companion type.
    
    URI: resource://metrics/companion_type/{companion_type}/timing
    
    Aggregates ONLY timing metrics from middleware for sessions using this companion type.
    For iteration counts, use session_resources instead.
    """
    
    sessions_with_companion = 0
    phase_durations_collected = {"draft": [], "critique": [], "revise": []}
    similarity_scores_collected = []
    convergence_sessions = 0
    phase_counts_total = {"draft": 0, "critique": 0, "revise": 0}
    
    # Scan all sessions for this companion type
    for session_id, session_data in session_manager.sessions.items():
        if companion_type in session_data.get("companions", {}):
            sessions_with_companion += 1
            
            # Get ONLY timing metrics from middleware (not run_log)
            middleware_state = session_data.get("middleware_state", {})
            metrics = middleware_state.get("metrics", {})
            
            if metrics:
                # Collect phase durations
                for phase, duration in metrics.get("average_durations", {}).items():
                    if phase in phase_durations_collected:
                        phase_durations_collected[phase].append(duration)
                
                # Collect phase counts from middleware
                for phase, count in metrics.get("phase_counts", {}).items():
                    if phase in phase_counts_total:
                        phase_counts_total[phase] += count
                
                # Get similarity from middleware (not run_log)
                if metrics.get("last_similarity_score") is not None:
                    similarity_scores_collected.append(metrics["last_similarity_score"])
                
                # Check convergence
                if metrics.get("convergence_detected"):
                    convergence_sessions += 1
    
    if sessions_with_companion == 0:
        return {
            "companion_type": companion_type,
            "message": f"No sessions found using companion type '{companion_type}'"
        }
    
    # Calculate timing statistics
    phase_timing = {}
    for phase, durations in phase_durations_collected.items():
        if durations:
            phase_timing[phase] = {
                "average_seconds": sum(durations) / len(durations),
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "samples": len(durations)
            }
    
    # Similarity analysis from middleware data
    similarity_metrics = {}
    if similarity_scores_collected:
        similarity_metrics = {
            "average": sum(similarity_scores_collected) / len(similarity_scores_collected),
            "min": min(similarity_scores_collected),
            "max": max(similarity_scores_collected),
            "samples": len(similarity_scores_collected)
        }
    
    return {
        "companion_type": companion_type,
        "sessions_analyzed": sessions_with_companion,
        "phase_timing": phase_timing,
        "phase_counts": phase_counts_total,
        "similarity_metrics": similarity_metrics if similarity_metrics else None,
        "convergence": {
            "sessions_with_convergence": convergence_sessions,
            "convergence_rate": convergence_sessions / sessions_with_companion
        },
        "note": "For iteration counts and companion state, use session_resources"
    }