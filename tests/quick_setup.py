#!/usr/bin/env python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# demos/quick_setup.py
"""
Quick-start smoke test
======================

Purpose
-------
• Verify that your local install, `OPENAI_API_KEY`, and template paths are
  wired correctly.  
• Show the absolute-minimum Companion workflow in <20 lines of code.

What it does
------------
1. Instantiates a *GenericCompanion* with GPT-4o-mini.
2. Runs one three-phase loop on a sample prompt.
3. Prints the final answer plus a terse view of the inner iterations.

Run
---
$ OPENAI_API_KEY=sk-…  python demos/quick_start.py
"""

import logging
from recursive_companion import GenericCompanion          # package import


# ── dial down unrelated library chatter ──────────────────────────
logging.basicConfig(level=logging.WARNING)

# ── 1. create the agent ──────────────────────────────────────────
agent = GenericCompanion(
    llm="gpt-4o-mini",
    verbose=False,             # no debug spam
    return_transcript=True,    # get run_log back with the answer
)

# ── 2. run one analysis ──────────────────────────────────────────
prompt = "We doubled support staff but response times got worse—why?"
final_answer, steps = agent.loop(prompt)

# ── 3. show results ──────────────────────────────────────────────
print("\n=== FINAL ANSWER ===\n")
print(final_answer)

print("\n=== INNER ITERATIONS ===\n")
print(agent.transcript_as_markdown())


#llm = ChatOpenAI(model_name="gpt-4o-mini")
#agent = GenericCompanion(llm, similarity_threshold=0.95, max_loops=2, verbose=False)

#question = "Our last release crashed during uploads and users are leaving."
#answer = agent.loop(question)
#print("\nFINAL RESULT:\n", answer)

