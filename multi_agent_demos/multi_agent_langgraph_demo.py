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
from langchain.runnables import RunnableLambda
from langchain.graphs import StateGraph
from recursive_companion import MarketingCompanion, BugTriageCompanion, StrategyCompanion

# 1 - Wrap in a RunnableLambda
llm_fast  = "gpt-4o-mini"
llm_deep  = "gpt-4.1-mini" 

mkt   = MarketingCompanion(llm=llm_fast, temperature=0.8, verbose=True)
bug   = BugTriageCompanion(llm=llm_deep, temperature=0.3)
plan = StrategyCompanion(llm=llm_fast, return_transcript=True)

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


# 3 - Inline LangGraph example (fan-in)
# No extra prompts, no schema gymnastics: simply passing text between the callables the classes already expose.
graph = StateGraph()
graph.add_node("marketing",    mkt_node)
graph.add_node("engineering",  bug_node)
graph.add_node("merge",        merge_node)
graph.add_node("strategy",     plan_node)

graph.add_edges(
    ("marketing",   "merge"),
    ("engineering", "merge"),
    ("merge",       "strategy"),
)

graph.set_entry_point("marketing", "engineering")
workflow = graph.compile()

final, steps = workflow.invoke(
    "App ratings fell to 3.2★ and uploads crash on iOS 17.2. Diagnose & propose next steps."
)

print("\n=== FINAL PLAN ===\n")
print(final)
print("\n=== INNER STEPS ===\n")
print(plan.transcript_as_markdown())
