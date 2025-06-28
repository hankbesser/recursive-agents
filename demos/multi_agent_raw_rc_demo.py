#!/usr/bin/env python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# demos/multi_agent_raw_rc_demo.py
"""
Multi-agent demo pipeline (Pure RC)
===================================
Runs a realistic workflow using pure Recursive Companion (no LangGraph):

1. **MarketingCompanion** - surfaces audience-level symptoms.
2. **BugTriageCompanion** - surfaces engineering/root-cause clues.
3. **StrategyCompanion** - merges both views into a single action plan.

Usage
-----
$ OPENAI_API_KEY=sk-...  python demos/multi_agent_raw_rc_demo.py

The script prints:
• Each domain-specific analysis (debug on for Marketing).
• The synthesised cross-functional action plan.

Edit the ``problem`` string or swap in other Companion subclasses to test
additional domains.
"""

from recursive_companion.base import MarketingCompanion
from recursive_companion.base import BugTriageCompanion
from recursive_companion.base import StrategyCompanion

# Multi-agent demo (shared problem → parallel lenses → synthesis)
# ---------------------------------------------------------------
problem = (
    "Since the last mobile release, picture uploads crash for many users, "
    "Instagram engagement is down 30 %, and our app-store rating fell to 3.2★. "
    "Why is this happening and what should we do?"
)

# 1) Independent domain analyses (different models / settings)
mkt   = MarketingCompanion(llm="gpt-4o-mini", temperature=0.9,max_loops=3, similarity_threshold=0.96, verbose=True)   # fast, cheap, show debug
bug   = BugTriageCompanion(llm="gpt-4.1-mini", temperature=0.25) # higher-context model

print("\n" + "=" * 80)
print("\n Pondering Marketing Analysis Verbose ON\n")
print("=" * 80)
mkt_view = mkt.loop(problem)

print("\n" + "=" * 80)
print("\nFinal Marketing Analysis (first 500 chars):")
print(mkt_view[:500] + "..." if len(mkt_view) > 500 else mkt_view)


print("\n" + "=" * 80)
print("\n Pondering Engineering Analysis Verbose OFF\n")
print("=" * 80)
bug_view = bug.loop(problem)


print("\nFinal Engineering Analysis (first 500 chars):")
print(bug_view[:500] + "..." if len(bug_view) > 500 else bug_view)


# 2) Merge perspectives for the synthesis step
combined_views = (
    "=== Marketing view ===\n"
    f"{mkt_view}\n\n"
    "=== Engineering view ===\n"
    f"{bug_view}\n\n"
    "Merge these perspectives and propose next actions."
)

# 3) Synthesis agent produces the cross-functional plan
synth = StrategyCompanion(llm="gpt-4o-mini", temperature=0.55)

print("\n" + "=" * 80)
print("\n Pondering a Sythesized Action Plan of Previous Views - Verbose OFF\n")
print("=" * 80)
action_plan = synth.loop(combined_views)



print("\nFinal Synthesized Action Plan - full thinking process in raw mardown:")
print(synth.transcript_as_markdown())


# Show convergence analysis
print("\n" + "=" * 80)
print("COMPLETE CONVERGENCE ANALYSIS")
print("=" * 80)

for name, agent in [("Marketing", mkt), ("Engineering", bug), ("Strategy", synth)]:
    print(f"\n{name} Companion:")
    print(f"  • Model: {agent.llm.model_name}")
    print(f"  • Temperature: {agent.llm.temperature}")
    print(f"  • Iterations: {len(agent.run_log)}/{agent.max_loops}")
    print(f"  • Similarity threshold: {agent.similarity_threshold}")
    
    # Determine convergence type
    last_critique = agent.run_log[-1]['critique'].lower()
    if "no further improvements" in last_critique or "minimal revisions" in last_critique:
        convergence = "Critique-based (no improvements needed)"
    elif len(agent.run_log) < agent.max_loops:
        convergence = "Similarity-based (threshold reached)"
    else:
        convergence = "Max iterations reached"
    print(f"  • Convergence: {convergence}")