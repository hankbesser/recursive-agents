#!/usr/bin/env python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# tests/test_runlog.py
from recursive_companion.base import GenericCompanion

# Create companion with verbose to see what's happening
companion = GenericCompanion(llm="gpt-4o-mini", max_loops=2, return_transcript=True)

# Run a simple test
print("=== Testing the RUN LOG CONTENTS -  pondering in process ===")
result, run_log = companion("What is 2+2?")

# Print what's in the run log
print("=== RUN LOG CONTENTS ===")
for i, step in enumerate(run_log, 1):
    print(f"\nIteration {i}:")
    print(f"Draft starts with: {step['draft'][:50]}...")
    print(f"Revision starts with: {step['revision'][:50]}...")
    
# Check if draft in iteration 2 matches revision from iteration 1
if len(run_log) > 1:
    print("\n=== COMPARISON ===")
    print(f"Iteration 1 revision == Iteration 2 draft? {run_log[0]['revision'] == run_log[1]['draft']}")
