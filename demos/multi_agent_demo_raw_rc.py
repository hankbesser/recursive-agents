#!/usr/bin/env python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# demos/multi_agent_demo_raw_rc.py
"""
Multi-agent demo pipeline
=========================
Runs a realistic workflow:

1. **MarketingCompanion** - surfaces audience-level symptoms.
2. **BugTriageCompanion** - surfaces engineering/root-cause clues.
3. **StrategyCompanion** - merges both views into a single action plan.

Usage
-----
$ OPENAI_API_KEY=sk-...  python -m companion.multi_agent_demo

The script prints:
• Each domain-specific analysis (debug on for Marketing).
• The synthesised cross-functional action plan.

Edit the ``problem`` string or swap in other Companion subclasses to test
additional domains.
"""

from recursive_companion import MarketingCompanion
from recursive_companion import BugTriageCompanion
from recursive_companion import StrategyCompanion

# Multi-agent demo (shared problem → parallel lenses → synthesis)
# ---------------------------------------------------------------
problem = (
    "Since the last mobile release, picture uploads crash for many users, "
    "Instagram engagement is down 30 %, and our app-store rating fell to 3.2★. "
    "Why is this happening and what should we do?"
)

# 1) Independent domain analyses (different models / settings)
mkt   = MarketingCompanion(llm="gpt-4o-mini", temperature=0.9, verbose=True)   # fast, cheap, show debug
bug   = BugTriageCompanion(llm="gpt-4.1-mini", temperature=0.25)                 # higher-context model

mkt_view = mkt.loop(problem)
bug_view = bug.loop(problem)

# 2) Merge perspectives for the synthesis step
combined_views = (
    "=== Marketing view ===\n"
    f"{mkt_view}\n\n"
    "=== Engineering view ===\n"
    f"{bug_view}\n\n"
    "Merge these perspectives and propose next actions."
)

# 3) Synthesis agent produces the cross-functional plan
synth          = StrategyCompanion(llm="gpt-4o-mini", temperature=0.55, return_transcript=True)
action_plan, _ = synth.loop(combined_views)

print("\n=== Synthesised action plan ===\n")
print(action_plan)
# print(synth.transcript_as_markdown())   # inner reasoning trail (optional)
