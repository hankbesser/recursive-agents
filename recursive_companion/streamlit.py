# streamlit.py
"""
Streamlit-enabled Companion Classes
===================================

Identical to base.py companions but with live UI updates during the
critique/revision loop. See base.py for detailed documentation of
each companion type.

These inherit from StreamlitBaseCompanion which adds progress_container
support for real-time updates in Streamlit apps.

Usage:
    from recursive_companion.streamlit import StreamlitMarketingCompanion
    
    container = st.container()
    agent = StreamlitMarketingCompanion(
        llm="gpt-4o-mini",
        progress_container=container
    )
    answer = agent("Why did engagement drop?")
    # User sees live updates in container during analysis
"""

from recursive_companion.template_load_utils import build_templates 
from core.streamlit_chains import StreamlitBaseCompanion


# All templates defined at module level
# System prompts include the shared protocol_context.txt
# (can change this behavior in template_load_utils.py if neededs)

# # Generic templates - defaults templates- no overrides
GENERIC_TEMPLATES = build_templates()

class StreamlitGenericCompanion(StreamlitBaseCompanion):
    """Generic companion with live updates"""
    TEMPLATES = GENERIC_TEMPLATES


# Marketing templates - override initial_sys
MARKETING_TEMPLATES = build_templates(initial_sys="marketing_initial_sys")

class StreamlitMarketingCompanion(StreamlitBaseCompanion):
    """Marketing companion with live updates"""
    TEMPLATES = MARKETING_TEMPLATES
    MAX_LOOPS = 2


# Bug triage templates - only override initial_sys
BUG_TRIAGE_TEMPLATES = build_templates(initial_sys="bug_triage_initial_sys")

class StreamlitBugTriageCompanion(StreamlitBaseCompanion):
    """Bug triage companion with live updates"""
    TEMPLATES = BUG_TRIAGE_TEMPLATES
    MAX_LOOPS = 3


# Strategy templates - only override initial_sys
STRATEGY_TEMPLATES = build_templates(initial_sys="strategy_initial_sys")

class StreamlitStrategyCompanion(StreamlitBaseCompanion):
    """Strategy companion with live updates"""
    TEMPLATES = STRATEGY_TEMPLATES
    SIM_THRESHOLD = 0.97