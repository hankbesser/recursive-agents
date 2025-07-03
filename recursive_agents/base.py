# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# recursive_agents/base.py
"""
Base Companion Classes for Recursive Agents Framework
========================================================

This module contains all standard companion implementations that inherit from
BaseCompanion. Each companion specializes in a different domain while sharing
the core 3-phase critique/revision loop.

Classes:
    GenericCompanion: Domain-agnostic baseline implementation
    MarketingCompanion: Growth and audience-sentiment focused
    BugTriageCompanion: Engineering-centric root cause analysis
    StrategyCompanion: Cross-functional synthesis and planning

Template Pattern:
    All companions share the same critique/revision templates by default.
    Each only overrides the initial_sys template to provide domain expertise.
    All templates are defined at module level
    System prompts include the shared protocol_context
    (You can change this behavior in template_load_utils.py if needed)
    See template_load_utils.py to customize this behavior.

Usage:
    from recursive_agents.base import MarketingCompanion
    
    agent = MarketingCompanion(llm="gpt-4o-mini", temperature=0.8)
    
    # Both work - __call__ is an alias for loop()
    answer = agent("Why did engagement drop...?")      # Concise
    answer = agent.loop("Why did engagement drop...?") # Explicit
"""


from recursive_agents.template_load_utils import build_templates 
from core.chains import BaseCompanion


# Generic templates - defaults templates- no overrides
GENERIC_TEMPLATES = build_templates()

class GenericCompanion(BaseCompanion):
    """
    Domain-agnostic companion for general analysis.
    
    Uses generic templates without specialization. Suitable for any
    problem domain where you don't need specific expertise.
    
    Inherits all defaults from BaseCompanion (3 loops, 0.98 similarity).

    Typical Usage
    -------------
    from recursive_agents.base import GenericCompanion
      
    # using loop() method with return_transcript
    generic = GenericCompanion(llm="gpt-4o-mini", return_transcript=True)
    answer, steps = generic.loop("Our Q3 revenue missed targets by 15%. analyze possible causes")
    
    print(f"Analysis: {answer}")
    print(f"Iterations: {len(steps)}")
    """
    TEMPLATES = GENERIC_TEMPLATES


# Marketing templates - override initial_sys
MARKETING_TEMPLATES = build_templates(initial_sys="marketing_initial_sys")

class MarketingCompanion(BaseCompanion):
    """
    Marketing-focused analysis with growth and audience insights.
    
    Specializes in:
    - Customer sentiment and engagement metrics
    - Funnel optimization and conversion analysis  
    - Campaign effectiveness and market positioning
    
    Uses fewer loops (2) for faster, more decisive marketing insights.

    Typical Usage
    -------------
    from recursive_agents.base import MarketingCompanion
    
    # using callable with temperature
    marketing = MarketingCompanion(llm="gpt-4o-mini", temperature=0.8)
    campaign_analysis = marketing("Black Friday campaign had 50% lower conversion than last year")
    
    print(campaign_analysis)
    """
    TEMPLATES = MARKETING_TEMPLATES
    MAX_LOOPS = 2
    
    # Note: Subclasses only need __init__ if adding new parameters.
    # Example:
    #
    # def __init__(self, llm=None, *, channel_weights=None, **kwargs):
    #     super().__init__(llm, **kwargs)  # Let parent handle all standard setup
    #     self.channel_weights = channel_weights or {"email": 1.0, "social": 1.0}



# Bug triage templates - only override initial_sys
BUG_TRIAGE_TEMPLATES = build_templates(initial_sys="bug_triage_initial_sys")

class BugTriageCompanion(BaseCompanion):
    """
    Engineering-focused companion for technical root cause analysis.
    
    Specializes in:
    - Reproducibility assessment and environment details
    - Impact scope and severity evaluation
    - Technical hypothesis generation
    
    Maintains default 3 loops for thorough technical investigation.

    Typical Usage
    -------------
    from recursive_agents.base import BugTriageCompanion
    
    # with similarity threshold and clear_history
    bug = BugTriageCompanion(
        llm="gpt-4.1-mini",   # Model flexibilty
        similarity_threshold=0.95,
        clear_history=True
    )
    bug_report = bug.loop("Login fails with 'undefined token' error after 5pm EST daily")
    """
    TEMPLATES = BUG_TRIAGE_TEMPLATES
    MAX_LOOPS = 3


# Strategy templates - only override initial_sys
STRATEGY_TEMPLATES = build_templates(initial_sys="strategy_initial_sys")

class StrategyCompanion(BaseCompanion):
    """
    Strategic synthesis companion for cross-functional planning.
    
    Designed to:
    - Integrate multiple perspectives (marketing + engineering)
    - Generate actionable recommendations
    - Balance competing priorities
    
    Lower similarity threshold (0.97) allows near-identical final
    drafts when perspectives already align well.
    
    Typical Multi-Agent Workflow 
    ----------------------------
    # Note: See multi_agent_demos/multi_agent_langgraph_demo.py for
    # LangGraph integration - companions as Runnables with zero code changes.

    from recursive_agents.base import MarketingCompanion
    from recursive_agents.base import BugTriageCompanion
    from recursive_agents.base import StrategyCompanion
   
    problem = "Users report app crashes on photo upload, engagement down 30%"

    marketing = MarketingCompanion(llm="gpt-4o-mini")
    marketing_view = marketing(problem)

    eng = BugTriageCompanion(llm="gpt-4o-mini")
    eng_view = eng(problem)

    # combining multiple views with verbose
    strategy = StrategyCompanion(llm="gpt-4o-mini",verbose=True)
    
    combined_issue = f''' 
    Marketing insight: {marketing_view[:200]}...
    Engineering findings: {eng_view[:200]}...

    Synthesize a action plan addressing both customer experience and technical stability.'''
    
    action_plan = strategy(combined_issue)
    print("=== FINAL STRATEGY ===")
    print(action_plan)
    """
    TEMPLATES = STRATEGY_TEMPLATES
    SIM_THRESHOLD = 0.97
