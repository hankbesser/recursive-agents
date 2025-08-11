# resources/metrics_resources.py
"""
Global metrics resources for learning and intelligence.

These resources expose the aggregated metrics collected by
PhaseIntelligenceMiddleware across all sessions.
"""

from typing import Dict, Any
from middleware.phase_intelligence import PhaseIntelligenceMiddleware

# We need a way to access the middleware instance
# This will be set by the server during initialization
_intelligence_middleware: PhaseIntelligenceMiddleware = None


def set_intelligence_middleware(middleware: PhaseIntelligenceMiddleware):
    """Set the middleware instance for metric access."""
    global _intelligence_middleware
    _intelligence_middleware = middleware


async def resource_global_metrics() -> Dict[str, Any]:
    """Get aggregated metrics across all sessions.
    
    URI: resource://metrics/global
    
    Returns metrics including:
    - Average iterations by companion type
    - Phase timing statistics
    - Convergence patterns
    - Content characteristics
    """
    if not _intelligence_middleware:
        return {
            "error": "Intelligence middleware not initialized",
            "metrics": {}
        }
    
    metrics = _intelligence_middleware.get_global_metrics()
    
    # Calculate summary statistics
    summary = {
        "total_sessions": sum(len(v) for v in metrics.get('avg_iterations_by_type', {}).values()),
        "companion_types_seen": list(metrics.get('avg_iterations_by_type', {}).keys()),
        "patterns_collected": len(metrics.get('convergence_patterns', [])),
    }
    
    # Add average timings if available
    for phase in ['draft', 'critique', 'revise']:
        key = f"{phase}_timings"
        if key in metrics and metrics[key]:
            timings = metrics[key]
            summary[f"avg_{phase}_time"] = sum(timings) / len(timings)
            summary[f"{phase}_samples"] = len(timings)
    
    return {
        "summary": summary,
        "metrics": metrics
    }


async def resource_companion_metrics(companion_type: str) -> Dict[str, Any]:
    """Get metrics for a specific companion type.
    
    URI: resource://metrics/companion/{companion_type}
    
    Returns companion-specific metrics including:
    - Average iterations
    - Typical patterns
    - Performance characteristics
    """
    if not _intelligence_middleware:
        return {
            "error": "Intelligence middleware not initialized",
            "companion_type": companion_type,
            "metrics": {}
        }
    
    metrics = _intelligence_middleware.get_global_metrics()
    
    # Extract companion-specific data
    companion_data = {
        "companion_type": companion_type,
        "iterations": []
    }
    
    # Get iteration data
    if companion_type in metrics.get('avg_iterations_by_type', {}):
        iterations = metrics['avg_iterations_by_type'][companion_type]
        companion_data['iterations'] = iterations
        companion_data['average_iterations'] = sum(iterations) / len(iterations) if iterations else 0
        companion_data['session_count'] = len(iterations)
    
    # Get patterns for this companion type
    patterns = [
        p for p in metrics.get('convergence_patterns', [])
        if p.get('companion_type') == companion_type
    ]
    companion_data['pattern_count'] = len(patterns)
    
    # Extract focus areas from patterns
    focus_areas = {}
    for pattern in patterns:
        if 'patterns' in pattern and 'focus_areas' in pattern['patterns']:
            for area in pattern['patterns']['focus_areas']:
                focus_areas[area] = focus_areas.get(area, 0) + 1
    
    companion_data['common_focus_areas'] = focus_areas
    
    return companion_data


async def resource_learning_suggestions() -> Dict[str, Any]:
    """Get AI-powered suggestions based on learned patterns.
    
    URI: resource://metrics/suggestions
    
    Returns suggestions for:
    - Optimal iteration counts
    - Temperature adjustments
    - Companion type selection
    """
    if not _intelligence_middleware:
        return {
            "error": "Intelligence middleware not initialized",
            "suggestions": []
        }
    
    metrics = _intelligence_middleware.get_global_metrics()
    suggestions = []
    
    # Suggest based on average iterations
    for companion_type, iterations in metrics.get('avg_iterations_by_type', {}).items():
        if iterations:
            avg = sum(iterations) / len(iterations)
            suggestions.append({
                "type": "iteration_prediction",
                "companion": companion_type,
                "message": f"{companion_type} typically completes in {avg:.1f} iterations",
                "confidence": "high" if len(iterations) > 5 else "medium"
            })
    
    # Suggest based on timing patterns
    for phase in ['draft', 'critique', 'revise']:
        key = f"{phase}_timings"
        if key in metrics and len(metrics[key]) > 10:
            timings = metrics[key]
            avg_time = sum(timings) / len(timings)
            suggestions.append({
                "type": "timing_expectation",
                "phase": phase,
                "message": f"{phase} phase typically takes {avg_time:.1f} seconds",
                "confidence": "high"
            })
    
    # Suggest based on convergence patterns
    patterns = metrics.get('convergence_patterns', [])
    if len(patterns) > 20:
        # Find most common focus areas
        all_focus_areas = {}
        for pattern in patterns:
            if 'patterns' in pattern and 'focus_areas' in pattern['patterns']:
                for area in pattern['patterns']['focus_areas']:
                    all_focus_areas[area] = all_focus_areas.get(area, 0) + 1
        
        if all_focus_areas:
            top_area = max(all_focus_areas, key=all_focus_areas.get)
            suggestions.append({
                "type": "common_pattern",
                "message": f"Most critiques focus on {top_area} ({all_focus_areas[top_area]} occurrences)",
                "confidence": "medium"
            })
    
    return {
        "suggestions": suggestions,
        "data_points": {
            "total_sessions": sum(len(v) for v in metrics.get('avg_iterations_by_type', {}).values()),
            "pattern_count": len(patterns)
        }
    }