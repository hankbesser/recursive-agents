#!/usr/bin/env python
# multi_agent_langgraph_demo.py
"""
Each node is now a first-class Runnable; there is built-in tracing, concurrency, retries, etc., 
without rewriting core/chain.py (the engine). In other words, 
Runnables/LangGraph are just an optional facade around the callables already implmented. 
They give observability, retries, and DAG routing when (and only when) needed, without forcing a redesign of the class-based core.


Why bother to do this?
    It shows exactly how LangGraph routing works.
    It proves the Companions are drop-in nodes (no refactor).
    The transcript printout lets users see Draft → Critique → Revision for the synthesis agent as well.

 Any Companion can now slot into LangChain tooling (RunnableLambda, Retry, StreamingWrapper, etc.) because of the  __call__ alias
"""
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph
from typing import TypedDict
from recursive_companion import MarketingCompanion, BugTriageCompanion, StrategyCompanion

# 1 - Wrap in a RunnableLambda
llm_fast  = "gpt-4o-mini"
llm_deep  = "gpt-4.1-mini" 

mkt   = MarketingCompanion(llm=llm_fast, temperature=0.8)
bug   = BugTriageCompanion(llm=llm_deep, temperature=0.3)
plan = StrategyCompanion(llm=llm_fast)

# Each node is now a first-class Runnable; you get built-in tracing, concurrency, retries, etc., without rewriting your engine.
mkt_node  = RunnableLambda(mkt)          # __call__ alias does the trick
bug_node  = RunnableLambda(bug)


# merge-lambda joins text views into one string
# note: LangGraph passes the entire upstream-state dict to a node.
# with out this function, two upstream nodes are piped straight into strategy, 
# so plan_node will receive a Python dict like {"engineering": "...", "marketing": "..."}.
# That's fine if your StrategyCompanion prompt expects that JSON blob, 
# but most of the time you'll want to concatenate the two strings first.
merge_node = RunnableLambda(
    lambda d: f"### Marketing\n{d['marketing']}\n\n### Engineering\n{d['engineering']}"
)
plan_node  = RunnableLambda(plan)


# Define the state schema for LangGraph
class GraphState(TypedDict):
    input: str
    marketing: str
    engineering: str
    merged: str
    final_plan: str

# Inline LangGraph example (fan-in)
# No extra prompts, no schema gymnastics: simply passing text between the callables the classes already expose.
graph = StateGraph(GraphState)
graph.add_node("marketing_agent",    lambda state: {"marketing": mkt_node.invoke(state["input"])})
graph.add_node("engineering_agent",  lambda state: {"engineering": bug_node.invoke(state["input"])})
graph.add_node("merge_agent",        lambda state: {"merged": merge_node.invoke(state)})
graph.add_node("strategy_agent",     lambda state: {"final_plan": plan_node.invoke(state["merged"])})

graph.add_edge("marketing_agent", "merge_agent")
graph.add_edge("engineering_agent", "merge_agent")
graph.add_edge("merge_agent", "strategy_agent")

graph.add_edge("__start__", "marketing_agent")
graph.add_edge("__start__", "engineering_agent")
graph.set_finish_point("strategy_agent")
workflow = graph.compile()

result = workflow.invoke(
    {"input": "App ratings fell to 3.2★ and uploads crash on iOS 17.2. Diagnose & propose next steps."}
)
final = result.get("final_plan", "")

print("\n=== FINAL PLAN ===\n")
print(final)
print("\n=== INNER STEPS ===\n")
print(plan.transcript_as_markdown())
