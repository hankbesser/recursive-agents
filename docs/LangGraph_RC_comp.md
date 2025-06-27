```python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.
```
# LangGraph & Recursive Companion: Complementary Observability

## The Power of Simple, Modular Design

**Recursive Companion agents are just callables** - no abstract base classes, complex interfaces, or framework lock-in:

```python
# Any companion is a simple callable
agent = MarketingCompanion()
result = agent("Why did sales drop?")  # That's it!

# Same agent works everywhere:
result = agent.loop("...")              # Explicit method
node = RunnableLambda(agent)           # LangGraph node
response = await agent_api(agent)       # Web service
```

Compare this to typical LangChain patterns that require learning multiple abstractions (Chains, Agents, Tools, Memory, etc.). RC focuses on **modular, composable design** where each piece does one thing well.

## Executive Summary

LangGraph and Recursive Companion solve different but complementary problems:

- **LangGraph** excels at **workflow orchestration** - managing how agents connect, execute in parallel, handle errors, and pass data between nodes. It's the industry standard for complex agent workflows.

- **Recursive Companion** provides **modular, transparent agents** - simple callables that show why they reach conclusions through visible critique/revision cycles. No framework lock-in, just functions that explain their thinking.

**Better Together**: RC companions work as drop-in LangGraph nodes, giving you both workflow orchestration AND thinking transparency with zero integration overhead.

## What Each Tool Does Best

### LangGraph's Strengths (Workflow Orchestration)

```python
# LangGraph excels at complex workflows
workflow = StateGraph()
workflow.add_conditional_edges(...)  # Conditional routing
workflow.stream(...)                 # Streaming execution
workflow.batch(...)                  # Batch processing

# With print_mode="debug", you see:
# - Task scheduling and execution order
# - Node inputs/outputs  
# - State transitions
# - Parallel execution timing
# - Error handling and retries
```

### Recursive Companion's Addition (Thinking Transparency)

```python
# RC adds introspection to any node
mkt = MarketingCompanion()
mkt_node = RunnableLambda(mkt)

# After workflow runs, access thinking history:
print(len(mkt.run_log))                    # Number of iterations
print(mkt.transcript_as_markdown())        # Full thinking process
print(mkt.run_log[-1]["critique"])         # Why it stopped iterating
# This data isn't available through LangGraph alone
```

## Observability Comparison

### LangGraph's Observability Features:

1. **Workflow Execution Visibility**
```python
# Debug mode prints workflow insights to stdout
for chunk in workflow.stream({"input": "..."}, print_mode="debug"):
    pass  # Debug info prints automatically, but isn't available as data
# Note: Debug output is text-only, not structured data
```

2. **State Management & Tracking**
```python
result = workflow.invoke({"input": "..."})
# Access complete state, all node outputs, transformations
```

3. **Visual Debugging & Graph Structure**
```python
graph.get_graph().draw_mermaid()  # Interactive workflow diagram
# Understand data flow, parallelism, dependencies
```

4. **Built-in Features**
- Streaming support for real-time monitoring
- Error handling and retry visibility  
- Conditional routing transparency
- Checkpointing and persistence

**Important Note**: Debug visibility comes at a cost - when using `print_mode="debug"`, the debug information is only printed to stdout as text. You cannot programmatically access this data, forcing you to choose between visibility (debug mode) or getting results (normal mode).

### What's Not Visible Without RC:

- ❓ **Reasoning Process**: Why did the agent reach this specific conclusion?
- ❓ **Iteration Details**: How many self-improvement cycles occurred?
- ❓ **Critique Content**: What specific feedback led to revisions?
- ❓ **Convergence Patterns**: Quality-based vs iteration limit?
- ❓ **Thinking Evolution**: How did understanding deepen over iterations?

**This isn't a LangGraph limitation** - they solve different problems. LangGraph excels at orchestration; RC adds reasoning transparency.

## Accessing Results: Debug Mode Trade-offs vs Always-Available Data

### LangGraph's Debug Mode Dilemma
```python
# Option 1: Debug mode for visibility
for chunk in workflow.stream(input, print_mode="debug"):
    pass  # Prints to stdout, but data isn't accessible programmatically
# Result: Can see what's happening, but can't access the actual results!

# Option 2: Normal mode for results  
result = workflow.invoke(input)
# Result: Get the final state, but no visibility into the process

# You must choose: visibility OR programmatic access, not both

# Debug output includes:
# [debug] task: When agents start
# [debug] task_result: When agents complete  
# But it's text with ANSI color codes - not structured data
```

### RC Direct Access (Simple & Complete)
```python
# Setup: Create RC agents (they maintain their own history)
mkt = MarketingCompanion()
eng = BugTriageCompanion()
strategy = StrategyCompanion()

# Use them in your workflow (LangGraph or standalone)
result = workflow.invoke(input)  # Normal execution, no debug mode needed

# Full visibility is always available on each agent:
mkt.run_log                         # Marketing's iteration history
eng.run_log                         # Engineering's iteration history
strategy.run_log                    # Strategy's iteration history

# Access any detail you need:
len(strategy.run_log)               # Number of iterations
strategy.run_log[-1]['critique']    # Final critique
strategy.transcript_as_markdown()   # Formatted thinking process

# Everything is a simple attribute - no parsing needed!
# No trade-offs: visibility and programmatic access together

# BONUS: Beautiful formatted output for humans
print(strategy.transcript_as_markdown())
# Outputs:
# ### Iteration 1
# **Draft**
# [Initial analysis...]
# **Critique**  
# [What could be improved...]
# **Revision**
# [Enhanced analysis...]
# ... (continues for all iterations)
```

## How Others Try to Add Observability

### The Fundamental Challenge
Without built-in introspection, developers face a difficult choice:
- Use debug mode to see what's happening (but lose programmatic access)
- Run normally to get results (but lose visibility)
- Try to build their own observability (complex and error-prone)

### Manual State Tracking (Painful!)
```python
# They have to manually build this:
class GraphState(TypedDict):
    input: str
    marketing: str
    marketing_iterations: list  # Manual tracking
    marketing_metadata: dict    # Manual tracking
    engineering: str
    engineering_iterations: list  # Manual tracking
    
def marketing_node(state):
    iterations = []
    for i in range(3):
        response = llm.invoke(...)
        iterations.append(response)  # Manual logging
    
    return {
        "marketing": response,
        "marketing_iterations": iterations  # Have to pass it along
    }
```

### Callbacks (Limited)
```python
from langchain.callbacks import FileCallbackHandler
handler = FileCallbackHandler("./logs.txt")
workflow.invoke({"input": "..."}, config={"callbacks": [handler]})
# Just logs raw LLM calls, no structure
```

### External Services (Expensive)
```python
# LangSmith - requires API key, costs money
# Still doesn't give you critique/revision cycles
```

## RC + LangGraph: Best of Both Worlds

### Setup (Zero Extra Work!)
```python
# Just wrap your companions
mkt = MarketingCompanion()
eng = BugTriageCompanion()
plan = StrategyCompanion()

mkt_node = RunnableLambda(mkt)
eng_node = RunnableLambda(eng)
plan_node = RunnableLambda(plan)
```

### What You Can Inspect (Automatically!)

```python
# After workflow runs
result = workflow.invoke({"input": "App crashed, users leaving"})

# 1. Overall flow (LangGraph)
print(result)  # Final outputs

# 2. Deep introspection PER NODE (RC magic)
print(f"Marketing iterations: {len(mkt.run_log)}")
print(f"Engineering iterations: {len(eng.run_log)}")
print(f"Strategy iterations: {len(plan.run_log)}")

# 3. Convergence analysis
for agent_name, agent in [("Marketing", mkt), ("Engineering", eng), ("Strategy", plan)]:
    last_critique = agent.run_log[-1]["critique"]
    if "no further improvements" in last_critique.lower():
        print(f"{agent_name}: Converged via critique")
    elif len(agent.run_log) < agent.max_loops:
        print(f"{agent_name}: Converged via similarity")
    else:
        print(f"{agent_name}: Hit max loops")

# 4. Quality metrics
def critique_quality(run_log):
    critiques = [step["critique"] for step in run_log]
    return {
        "total_iterations": len(critiques),
        "avg_critique_length": sum(len(c) for c in critiques) / len(critiques),
        "converged_early": len(critiques) < 3
    }

print("Marketing quality:", critique_quality(mkt.run_log))
print("Engineering quality:", critique_quality(eng.run_log))

# 5. Full thinking traces - BEAUTIFULLY FORMATTED!
# No parsing, no JSON manipulation - just readable markdown
print("\n=== MARKETING THOUGHT PROCESS ===")
print(mkt.transcript_as_markdown())  # Ready for reports, logs, or UI display!

print("\n=== ENGINEERING THOUGHT PROCESS ===")
print(eng.transcript_as_markdown())  # Each iteration clearly separated

print("\n=== STRATEGY SYNTHESIS PROCESS ===")
print(plan.transcript_as_markdown())  # Draft → Critique → Revision for each loop
```

## Specific Code Comparisons

### Task: Debug why an agent made a decision

**Pure LangGraph:**
```python
# You get nothing
result = workflow.invoke({"input": "..."})
print(result["marketing"])  # Just the final text
# WHY did it say this? 🤷‍♂️
```

**With RC:**
```python
result = workflow.invoke({"input": "..."})
# See EVERYTHING
for i, step in enumerate(mkt.run_log):
    print(f"\nIteration {i+1}:")
    print(f"Critique: {step['critique'][:100]}...")
    print(f"Key change: {identify_key_change(step['draft'], step['revision'])}")
```

### Task: Compare agent performance

**Pure LangGraph:**
```python
# Have to add timing manually
import time
start = time.time()
result = workflow.invoke(...)
print(f"Took {time.time() - start}s")
# But how many iterations? What was the thinking quality? 🤷‍♂️
```

**With RC:**
```python
result = workflow.invoke(...)

# Rich performance data
for name, agent in [("mkt", mkt), ("eng", eng), ("plan", plan)]:
    print(f"\n{name}:")
    print(f"  Iterations: {len(agent.run_log)}")
    print(f"  Convergence: {agent.run_log[-1].get('similarity', 'critique-based')}")
    print(f"  Final critique: {agent.run_log[-1]['critique'][:50]}...")
```

### Task: A/B test different approaches

**Pure LangGraph:**
```python
# Run twice, compare final outputs only
result_a = workflow_a.invoke(input)
result_b = workflow_b.invoke(input)
# Which thinking process was better? No idea! 🤷‍♂️
```

**With RC:**
```python
# Run both workflows
result_a = workflow_a.invoke(input)
result_b = workflow_b.invoke(input)

# Compare thinking patterns
print(f"Workflow A: {len(plan_a.run_log)} iterations")
print(f"Workflow B: {len(plan_b.run_log)} iterations")

# Compare critique quality
critiques_a = [s["critique"] for s in plan_a.run_log]
critiques_b = [s["critique"] for s in plan_b.run_log]

print(f"A critique specificity: {measure_specificity(critiques_a)}")
print(f"B critique specificity: {measure_specificity(critiques_b)}")
```

## What This Means for Production Systems

### Debugging Production Issues

**Without RC:**
- "The strategy agent gave bad advice"
- No way to know why
- Add logging everywhere (tedious)
- Still can't see thinking evolution

**With RC:**
```python
# In production, after a bad result:
print(plan.transcript_as_markdown())
# Immediately see:
# - Initial draft was too vague
# - Critique caught the issue
# - Revision still missed key point
# - Second critique identified root cause
# - Final revision addressed it
```

### Performance Monitoring

**Without RC:**
- Track execution time
- Count tokens
- That's about it

**With RC:**
```python
# Rich metrics for monitoring
metrics = {
    "agent": "strategy",
    "iterations": len(plan.run_log),
    "convergence_type": "similarity" if len(plan.run_log) < plan.max_loops else "max_loops",
    "critique_evolution": [len(s["critique"]) for s in plan.run_log],
    "thinking_depth": sum(len(s["revision"]) for s in plan.run_log)
}
```

## The Synergy: Better Together

**LangGraph Excels At:**
- 🔀 Complex workflow orchestration
- ⚡ Parallel execution and streaming
- 🔄 State management and persistence
- 🎯 Conditional routing and error handling
- 📊 Workflow-level debugging

**Recursive Companion Adds:**
- 🧠 Thinking process transparency
- 🔍 Critique/revision audit trails
- 📈 Convergence metrics and patterns
- 💡 Reasoning evolution tracking
- 🎭 Decision rationale capture

**Together = Complete Observability:**
- See both the workflow (LangGraph) AND the thinking (RC)
- Debug both orchestration issues AND reasoning problems
- Understand both what happened AND why it happened
- Zero integration overhead - RC companions are drop-in nodes

Your companions become "thoughts-included" nodes that enhance any LangGraph workflow with deep introspection capabilities.

## Code You Can Run Right Now

```python
# Standard LangGraph - opaque nodes
def basic_node(state):
    return {"output": llm.invoke(state["input"])}

# RC-powered - transparent nodes
companion = MarketingCompanion()
def rc_node(state):
    result = companion(state["input"])
    # Later can access: companion.run_log, companion.transcript_as_markdown()
    return {"output": result}

# After graph runs:
# Basic: ¯\_(ツ)_/¯ 
# RC: Full thinking history available!
```

This demonstrates the complementary nature: LangGraph provides the orchestration framework, while RC transforms nodes from black boxes into glass box thinking engines. Use both for complete system understanding.