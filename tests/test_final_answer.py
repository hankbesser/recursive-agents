#!/usr/bin/env python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# tests/test_final_answer.py
from recursive_companion.base import GenericCompanion

# Create companion with 2 loops
companion = GenericCompanion(llm="gpt-4o-mini", max_loops=2, return_transcript=True)

# Run a simple test
print("=== Running final answer match test-  pondering in process===\n")
final_answer, run_log = companion("What is 2+2?")

print("=== CHECKING IF FINAL ANSWER MATCHES LAST REVISION ===\n")

# Get the last revision from run_log
last_revision = run_log[-1]["revision"]

print(f"Last revision text:\n{last_revision}\n")
print(f"Final answer text:\n{final_answer}\n")

# Check if they're the same
if final_answer == last_revision:
    print("✅ CORRECT: Final answer EQUALS last revision")
else:
    print("❌ BUG: Final answer is DIFFERENT from last revision!")
    print("\nDifference found!")
    
# Also show all revisions for clarity
print("\n=== ALL REVISIONS ===")
for i, step in enumerate(run_log):
    print(f"\nIteration {i+1} revision:\n{step['revision']}")
    
print(f"\nFinal answer returned by function:\n{final_answer}")
