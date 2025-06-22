#!/usr/bin/env python
# langgraph_example.py
"""
Proper LangGraph integration showing multi-agent workflow with state management.

This demonstrates how the Recursive Companion framework integrates with LangGraph:
1. Each companion is already a callable (thanks to __call__ method)
2. No adapters or wrappers needed - companions ARE functions
3. LangGraph handles the orchestration, companions handle the thinking
"""
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from recursive_companion import MarketingCompanion, BugTriageCompanion, StrategyCompanion

# Define the graph state - this is what gets passed between nodes
# LangGraph uses TypedDict to define the "memory" that flows through the graph
class AgentState(TypedDict):
    problem: str                    # The initial problem statement
    marketing_analysis: str         # Marketing companion's analysis
    engineering_analysis: str       # Bug triage companion's analysis
    combined_analysis: str          # Merged perspectives
    final_strategy: str            # Strategy companion's final plan
    messages: List[str]            # Audit trail of what happened

# Initialize companions - these are just regular companion instances
# The magic: they're already callables, so they work as graph nodes!
mkt = MarketingCompanion(llm="gpt-4o-mini", temperature=0.8)
bug = BugTriageCompanion(llm="gpt-4o-mini", temperature=0.3)
strategy = StrategyCompanion(llm="gpt-4o-mini", return_transcript=True)

# Define node functions - these wrap our companions for the graph
# Each node:
# 1. Takes the current state
# 2. Calls the companion (which is just a function!)
# 3. Returns updates to the state
def marketing_node(state: AgentState):
    """Marketing analysis node - focuses on customer/market perspective"""
    # Call the marketing companion - it's just mkt(problem)!
    analysis = mkt(state["problem"])
    
    # Return state updates - LangGraph merges these into the state
    return {
        "marketing_analysis": analysis,
        "messages": state.get("messages", []) + ["Marketing completed analysis"]
    }

def engineering_node(state: AgentState):
    """Engineering analysis node - focuses on technical root causes"""
    # Call the bug triage companion - again, just a function call
    analysis = bug(state["problem"])
    
    return {
        "engineering_analysis": analysis,
        "messages": state.get("messages", []) + ["Engineering completed analysis"]
    }

def combine_node(state: AgentState):
    """Combine both analyses - this is just string formatting, no AI needed"""
    # Simple text merge - we just format both analyses together
    combined = f"""### Marketing Analysis
{state['marketing_analysis']}

### Engineering Analysis
{state['engineering_analysis']}

Based on these perspectives, create a unified strategy."""
    
    return {
        "combined_analysis": combined,
        "messages": state.get("messages", []) + ["Analyses combined"]
    }

def strategy_node(state: AgentState):
    """Create final strategy using the Strategy companion"""
    # The strategy companion returns a tuple (final_answer, run_log)
    # because we set return_transcript=True
    final, _ = strategy(state["combined_analysis"])
    
    return {
        "final_strategy": final,
        "messages": state.get("messages", []) + ["Strategy formulated"]
    }

# Build the graph - this is where LangGraph shines
# We're defining a workflow as a directed graph
workflow = StateGraph(AgentState)

# Add nodes - each node is just a function that takes state and returns state updates
workflow.add_node("marketing", marketing_node)
workflow.add_node("engineering", engineering_node)
workflow.add_node("combine", combine_node)
workflow.add_node("strategy", strategy_node)

# Define the flow - this creates the execution path
# START -> marketing & engineering (parallel) -> combine -> strategy -> END

# Set entry points - both marketing and engineering start in parallel
workflow.add_edge("__start__", "marketing")
workflow.add_edge("__start__", "engineering")

# Add edges - define how data flows through the graph
workflow.add_edge("marketing", "combine")      # Marketing results go to combine
workflow.add_edge("engineering", "combine")    # Engineering results go to combine  
workflow.add_edge("combine", "strategy")       # Combined analysis goes to strategy
workflow.add_edge("strategy", END)             # Strategy is the final step

# Compile the graph - this creates an executable workflow
# The compiled app handles:
# - Parallel execution
# - State management
# - Error handling
# - Retries (if configured)
app = workflow.compile()

# Run the workflow - this shows the power of the integration
if __name__ == "__main__":
    # Define the problem we want to analyze
    problem = "App ratings fell to 3.2★ and uploads crash on iOS 17.2. Diagnose & propose next steps."
    
    # Invoke the graph with initial state
    # LangGraph will:
    # 1. Run marketing and engineering nodes IN PARALLEL
    # 2. Wait for both to complete
    # 3. Run combine node
    # 4. Run strategy node
    # 5. Return the final state with all results
    result = app.invoke({
        "problem": problem,
        "messages": ["Starting analysis"]
    })
    
    # Display the execution trail
    print("=== WORKFLOW EXECUTION ===")
    for msg in result["messages"]:
        print(f"✓ {msg}")
    
    # Show the final strategy
    print("\n=== FINAL STRATEGY ===")
    print(result["final_strategy"])
    
    # Show metrics to demonstrate what happened
    print("\n=== TRACE ===")
    print(f"Marketing: {len(result['marketing_analysis'])} chars")
    print(f"Engineering: {len(result['engineering_analysis'])} chars")
    print(f"Combined: {len(result['combined_analysis'])} chars")
    print(f"Strategy: {len(result['final_strategy'])} chars")
    
    # The key insight: Your companions didn't need ANY modification to work
    # with LangGraph. They're just functions, so they plug right in!
    print("\n💡 Key insight: Companions are callables, so they work everywhere!")
