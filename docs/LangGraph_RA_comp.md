```python
# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.
```
# LangGraph & Recursive Agents: Complete Agent Observability

## The Missing Piece in Agent Development

When an LLM agent produces unexpected output, developers need to understand both what happened and why. Current tools excel at workflow orchestration but lack visibility into agent reasoning.

Recursive Agents fills this gap. RA agents are Python callables that automatically maintain their complete thinking history - every iteration, critique, and refinement is preserved for inspection.

### Clean Architecture

RA takes a different approach - no complex class hierarchies, no message schemas, no framework-specific primitives:

```python
# RA: Just a callable
agent = MarketingCompanion()
result = agent("Why did sales drop?")  # That's it!

# Compare to typical LangChain patterns:
# - Need SystemMessage, HumanMessage, AIMessage classes
# - Must understand Chains, Agents, Tools, Memory abstractions
# - Requires specific invoke() patterns and schemas
# - Deep nesting: chain.steps[0].agent.memory.messages[0].content

# RA works everywhere without modification:
result = agent.loop("...")              # Direct call
node = RunnableLambda(agent)           # Instant LangGraph node
response = await agent_api(agent)       # Web service ready
```

**No nested data structures**. Access what you need directly: `agent.run_log`, `agent.history`. No digging through layers of abstractions.

## Executive Summary

Building reliable AI systems requires understanding both workflow execution and agent reasoning. Today's tools only solve half this equation.

- **LangGraph** excels at **workflow orchestration** - managing how agents connect, execute in parallel, handle errors, and pass data between nodes. It shows you the "what" of your system.

- **Recursive Agents** provides **thinking transparency** - agents that automatically maintain their complete reasoning history through iterative refinement. It shows you the "why" behind every decision.

**The Key Insight**: RA agents work as drop-in LangGraph nodes. You don't choose between tools - you get workflow orchestration AND thinking transparency in one system.

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

### Recursive Agents's Addition (Thinking Transparency)

```python
# RA adds introspection to any node
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
# stream_mode="debug" provides structured debug events
for chunk in workflow.stream({"input": "..."}, stream_mode="debug"):
    # chunk is a dict with type, timestamp, payload
    print(chunk)  # {'type': 'task', 'payload': {...}}
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

**Important Note**: While `stream_mode="debug"` provides structured debug events, you still need to parse nested payloads to extract specific information. The debug stream shows workflow orchestration details but doesn't include agent reasoning, critique/revision cycles, or convergence patterns.

### Key Differences

Standard LangChain/LangGraph patterns involve:
- SystemMessage, HumanMessage, AIMessage classes
- TypedDict schemas and nested payloads
- Framework-specific patterns
- Deep nesting: `workflow.nodes[0].state['messages'][0].content`

RA provides:
- Direct access: `agent.run_log`, `agent.history`
- Universal compatibility across environments
- String in, string out interface
- Automatic history tracking

## Accessing Results: Structured Debug Data vs Always-Available Introspection

### LangGraph's Debug Stream Approach
```python
# Using stream_mode="debug" for structured debug data
debug_chunks = []
for chunk in workflow.stream(input, stream_mode="debug"):
    debug_chunks.append(chunk)  # Capture structured debug events

# You get debug events like:
# {'type': 'task', 'payload': {'name': 'agent_name', ...}}
# {'type': 'task_result', 'payload': {'result': [(...)]}}

# But to extract specific results requires parsing:
for chunk in debug_chunks:
    if chunk.get('type') == 'task_result':
        # Navigate nested structure to find what you need
        pass

# Note: Still no access to agent reasoning or iterations
```

### RA Direct Access (Automatic & Complete)

The key difference: RA agents automatically maintain their history with zero configuration.

```python
# Create agents - that's it, introspection is built-in
mkt = MarketingCompanion()
eng = BugTriageCompanion()
strategy = StrategyCompanion()

# Use normally - no special flags, modes, or configuration
result = workflow.invoke(input)  

# Complete history is automatically available:
mkt.run_log                         # Every iteration preserved
eng.run_log                         # All critiques and revisions
strategy.run_log                    # Full thinking evolution

# Direct access to any detail:
len(strategy.run_log)               # Iteration count
strategy.run_log[-1]['critique']    # Why it stopped
strategy.transcript_as_markdown()   # Human-readable history

# Zero overhead, always on, no trade-offs

# BONUS: Formatted output ready for humans
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

Without built-in introspection, developers resort to painful workarounds:

**Option 1: Manual State Tracking**  
Add custom fields to TypedDict schemas, implement logging in every node, and carefully pass metadata through the entire graph. Complex, error-prone, and still incomplete.

**Option 2: Callbacks**  
```python
from langchain.callbacks import FileCallbackHandler
handler = FileCallbackHandler("./logs.txt")
workflow.invoke({"input": "..."}, config={"callbacks": [handler]})
# Just logs raw LLM calls, no structured thinking history
```

**Option 3: External Services**  
```python
# LangSmith - requires API key, costs money
# Still doesn't capture iterative refinement process
```

None of these approaches provide the automatic, structured thinking history that RA delivers out of the box.

## RA + LangGraph: Best of Both Worlds

### Zero-Friction Integration

```python
# Create companions
mkt = MarketingCompanion()
eng = BugTriageCompanion()
plan = StrategyCompanion()

# Use with LangGraph
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

# 2. Direct attribute access - no digging through nested structures
print(f"Marketing iterations: {len(mkt.run_log)}")  # Straightforward!
print(f"Final output: {mkt.history[-1].content}")   # Direct!

# Compare to typical LangChain access patterns:
# state['nodes']['marketing']['memory']['chat_memory']['messages'][-1]['content']
# workflow.memory.chat_memory.messages[-1].content
# chain.steps[0].outputs[0].generations[0][0].text

# 3. Everything is just attributes on the agent instance
mkt.run_log          # Complete history
mkt.history          # Conversation memory
mkt.llm              # The actual model
mkt.max_loops        # Configuration
# No framework wrappers, no nested state, no schemas

# 4. Full thinking traces
print(mkt.transcript_as_markdown())  # Complete reasoning history
print(eng.transcript_as_markdown())  # All iterations preserved
print(plan.transcript_as_markdown())  # Synthesis process visible
```


## Real-World Impact

### Case 1: Production Debugging

Your customer success agent gives inappropriate advice. With standard tools, you're blind. With RA:

```python
# Instant root cause analysis
print(agent.transcript_as_markdown())

# Output shows:
# Iteration 1: Agent misunderstood context
# Critique: "Missing customer's actual pain point"
# Iteration 2: Better but still generic
# Critique: "Needs specific technical details"
# Iteration 3: Addressed the real issue

# Now you know exactly what went wrong and can fix it
```

### Case 2: Quality Assurance

You need to ensure agents meet quality standards before deployment:

```python
def validate_agent_quality(agent, test_cases):
    for test in test_cases:
        agent(test.input)
        
        # Check reasoning quality
        if len(agent.run_log) == 1:
            print(f" No refinement for: {test.input}")
        
        # Verify critique thoroughness
        critiques = [step["critique"] for step in agent.run_log]
        if any(len(c) < 100 for c in critiques):
            print(f" Shallow critique detected")
            
        # Ensure convergence quality
        if len(agent.run_log) >= agent.max_loops:
            print(f" Hit iteration limit - may need tuning")
```

### Performance Monitoring

**Without RA:**
Track execution time and token counts. That's about it.

**With RA:**
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

**Together = Complete Observability:**
- See both the workflow (LangGraph) AND the thinking (RA)
- Zero integration overhead - RA agents work directly as LangGraph nodes

Your companions become "thoughts-included" nodes that enhance any LangGraph workflow with deep introspection capabilities.


## Start Building Transparent AI Systems Today

Recursive Agents transforms opaque LLM calls into transparent reasoning processes. Whether you're debugging production issues, ensuring quality standards, or optimizing agent performance, RA gives you the visibility you need. The future of AI development isn't about choosing between tools - it's about combining the right ones. LangGraph handles the "what," RA reveals the "why," and together they enable more observable AI systems.