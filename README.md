# Recursive Companion 🔄

## A Meta-Framework for Self-Improving Agents

Recursive Companion implements a **three-phase iterative refinement architecture** where LLM agents (instances of Classes) critique and improve their own outputs. Unlike single-pass systems, each agent automatically tracks its full revision history, making every decision inspectable and debuggable.

![Sequence Flow](images/Sequence_Summary.svg)

→ See the [Architecture Documentation](docs/RC_architecture.md) for detailed system design.

### Why Recursive Companion?

**See inside the thinking.*** While other frameworks show you what happened, RC shows you why. Every instance maintains a complete audit trail of its critique-revision cycles, stopping conditions, and decision rationale. This transparency is built-in, not bolted on.

*Unlike single-shot responses, agents systematically refine their outputs by critiquing and improving their own work—thinking about their thinking.

**Flexible template loading.** The `build_templates()` utility lets you compose analytical patterns: override just what changes (usually only initial system template per domain), apply overarching protocols to specific phases (usually throughout system templates in all realted domains for consistent behavior), or skip protocols entirely. System templates define WHO the agent is, user templates define WHAT task to perform, and protocols shape HOW to analyze—each layer independently configurable.


---

## What Makes RC Unique

| Code Pattern | Why It Matters | Rare in OSS? |
|--------------|----------------|--------------|
| **`Draft\|LLM → Critique\|LLM → Revision\|LLM` chains built once** | Three-phase self-improvement is automatic - no manual wiring | ✓✓ |
| **One `protocol_context.txt` feeds all system prompts** | Change reasoning style everywhere with one edit | ✓ |
| **Templates live as `.txt` files on disk** | Git tracks prompt changes; hot-reload without restarting | ✓ |
| **New expert domain = inherit BaseCompanion + point to template** | Three lines of code gets you a complete agent | ✓✓ |
| **Every companion works as `agent()` or `RunnableLambda(agent)`** | Same object works standalone or in any framework | ✓ |
| **Built-in `run_log` tracks all iterations** | See why decisions were made without adding instrumentation | ✓✓ |

✓ = Uncommon in open source projects | ✓✓ = Very rare in open source projects

For detailed comparison with LangGraph capabilities, see [LANGGRAPH_COMPARISON.md](docs/LANGGRAPH_COMPARISON.md).

---
### 🔧 Quick Clone

```bash
# Create conda environment
conda create -n recursive-companion python=3.12 -y # (or python=3.13 -y)
conda activate recursive-companion
# Or using venv
# python -m venv venv
# source venv/bin/activate  

# clone and install
git clone https://github.com/yourusername/recursive-companion.git
cd recursive-companion
pip install -e .  # or pip install . for non-editable
```  
---
### 🤖 Challenge: Ask Your Agentic Coding tool to Think Deeply about this Project

Here's something fun - ask your favorite coding tool ( i.e. Claude Code in a terminal) the following input prompt in a new conversation.. It is very informal and you can taylor the structure (possibly more formal language if you are into that) but the TODO is pretty solid with this particular order:

**"Ok please think as deeply as possible about this project. Start with the README and docs folder to get a sense of it... now thinking as deeply as you possibly can, analyze the package. The main core engine is in core/chains.py - think deeply about this, giving every detail you can see from it and what it does. Then go to the package level in recursive_companion including template_load_utils.py and base.py and do the same deep thinking process. Then read the templates folder starting with the protocol, then system prompts (noting that protocol language won't leak as an aside), then the user prompts. Finally hit the demos folder - again, every detail and deep analysis you can.  It's good to get a deep grasp of this project before moving on. (Skip the streamlit files for now - those are separate and powered by the same code base).  Thank you!"**

*The responses will not dissapoint.*

---


## 🏗️ Architecture: Clean Layers, Clear Purpose
→ See the [Architecture Documentation](docs/RC_architecture.md)

```text
Your Code
    ↓ imports
recursive_companion/        # Pick your companion
    ├── base.py             # Standard: Marketing, Bug, Strategy, Generic
    └── streamlit.py        # Same companions + live UI updates
        ↓ inherits
core/chains.py              # The engine: 3-phase loop, convergence, history
        ↓ uses
templates/*.txt             # Hot-swappable prompts + protocol injection
```
**Where to Look (Separation of Concerns):**

- **Engineers** → ```core/chains.py``` (how to build the chains, storage/caching/memory management, observability, iteration process, etc.)
- **Users** → ```recursive_companion/base.py``` (picking companions)
- **Prompt Engineers** → ```templates/``` folder + ```template_load_utils.py```
- **UI Developers** → ```streamlit.py``` (progress containers)
- *or any combination of these*

💡 **Tip:** Each module includes extensive docstrings explaining design decisions, usage patterns, and implementation details. Start with the docstrings for a comprehensive understanding. 


---
## 📚 Three Levels of Understanding

### Level 1: Just Use It (5 minutes)
```python
from recursive_companion import MarketingCompanion

agent = MarketingCompanion("gpt-4o-mini")
answer = agent("Why did engagement drop 30%?")
# Done. The agent critiques itself, refines, and converges.

# note: answer = agent("Why did engagement drop 30%?") gives same results as
#       answer = agent.loop("Why did engagement drop 30%?") 

# this means any Companion can now slot into different tooling frameworks  
# because of the  __call__ alias
```

### Level 2: Compose & Customize (30 minutes)
```python
# Pick your domain, tweak your parameters
marketing = MarketingCompanion(temperature=0.8, max_loops=2)
engineering = BugTriageCompanion(similarity_threshold=0.95)

# Orchestrate multi-agent workflows
synthesis = StrategyCompanion()
plan = synthesis(f"{marketing(problem)} + {engineering(problem)}")

# Or plug into LangGraph with zero changes
from langchain.runnables import RunnableLambda
marketing_node = RunnableLambda(marketing)  # It's a Runnable!
```
### Level 3: Extend the Framework (2 hours)

```python
# Create new domains by overriding one template - 
# the domains intial system template
LEGAL_TEMPLATES = build_templates(initial_sys="legal_initial_sys")
class LegalCompanion(BaseCompanion):
    TEMPLATES = LEGAL_TEMPLATES
    SIM_THRESHOLD = 0.99  # Legal requires higher precision
```
## 🚀 Quick Start - Full Streamlit App


```bash
export OPENAI_API_KEY="sk-..." # in terminal
# For Jupyter/Python (more secure):
# Create .env file with:
# OPENAI_API_KEY="sk-..."
# Then in your code:
# from dotenv import load_dotenv
# load_dotenv()
```

### Run the Complete Streamlit Application
```bash
streamlit run streamlit_app.py
```

**You get a full interactive application:**
- Select any companion type from the dropdown
- Enter your prompt and watch the AI refine its response
- See critique-revision cycles happen in real-time
- View cosine similarity scores update live
- Export results with one click

This is a full testing and observability app included with the framework.

### Other Examples
```bash
# Minimal example
python demos/quick_setup.py

# Multi-agent orchestration
python multi_agent_demos/multi_agent_demo_raw_rc.py

# LangGraph integration
python multi_agent_demos/multi_agent_langgraph_demo.py
```
---


## Why This Architecture Matters

1. **Mathematical Convergence > Arbitrary Limits**
    - Not "stop after 3 tries"
    - Stop when `cosine_from_embeddings(revision[n-1], revision[n]) > 0.98`
2. **Companions as Callables = Composability**
- Works in Jupyter: `agent("question")`
- Works with LangGraph: `RunnableLambda(agent)`
- Works in Streamlit: Live visualization of critique-revision cycles!
3. **Templates as Data = Evolution Without Refactoring**
- Change prompts in production
- A/B test different protocols
- Domain experts can contribute without coding

### Multi-Agent Orchestration

#### **Raw Python** (Sequential):
```python
# multi_agent_demo_raw_rc.py
mkt_view = mkt.loop(problem)
bug_view = bug.loop(problem)
action_plan = synth.loop(combined_views)
```
#### **LangGraph** (DAG with parallelism):
```python
# multi_agent_langgraph_demo.py

graph = StateGraph()
graph.add_edges(
    ("marketing", "merge"),
    ("engineering", "merge"),
    ("merge", "strategy")
)
# Companions need ZERO changes to work as graph nodes!
```
### Other Examples
```bash
# Minimal example
python demos/quick_setup.py
```
---
## 🔧 Production Features

#### Observability

- **Verbose mode**: prints every phase of thinking live
- **Transcript capture**: return full run_log for debugging along with the final analysis (the instatiated object will have have it own run_log though)
- **Standard logging**: Integration-ready

### Efficiency

- **Token optimization**: No system prompt in history
- **Smart caching**: Single embeddings client
- **Early exit**: Stop when converged, not exhausted

### Flexibility

- **Any OpenAI model**: "gpt-4o-mini", "gpt-4.1", custom endpoints
- **Configurable everything**: Per-instance overrides
- **Template hot-reload:** Change prompts without code

---

## 🎓 The Strategic Decomposition Protocol

Read ```templates/protocol_context.txt``` to see the structured reasoning framework that guides agents through:

- Multi-layered problem analysis
- Iterative pattern recognition
- Systematic refinement cycles

This structured approach to recursive problem decomposition consistently outperforms single-pass analysis.

---


### 📝 Creating Your Own Companion

### 1. Write your
```text
# templates/financial_initial_sys.txt
{context}  # Protocol automatically injected

You are a Financial Analysis Companion. Focus on:
- Cash flow patterns and anomalies
- Risk indicators and market conditions
- Regulatory compliance implications
```

### 2. Create the companion class
```python
your_app/companions.py
from recursive_companion import BaseCompanion
from recursive_companion.template_load_utils import build_templates

class FinancialCompanion(BaseCompanion):
    TEMPLATES = build_templates(initial_sys="financial_initial_sys")
    MAX_LOOPS = 4  # Financial analysis needs thoroughness
    TEMPERATURE = 0.3  # Lower temperature for numerical precision
```

### 3. Use it anywhere
```python
fin = FinancialCompanion()

# note: callable - __call__ is an alias for loop()
analysis = fin("Q3 revenue variance exceeds 2 standard deviations") 
```
---

---

*Agents that refine their responses through iteration, integrated seamlessly into your existing code.*

**License**

MIT

**Contributing**

PRs welcome! See our ```CONTRIBUTING.md```.

## 🔮 Future Explorations

The Recursive Companion framework opens fascinating research directions:

- Advanced convergence analysis beyond embeddings / cosine similarity
- Richer integration patterns with agentic frameworks
- Extended observability for multi-loop systems

We're particularly interested in collaborations exploring how recursive
patterns emerge across different domains and scales.



## Bonus Section: This README's design philosophy

1. **Three-level structure** mirrors the codebase organization
2. **Technical depth** with actual code snippets and architecture diagrams
3. **Clear separation** of who should look where (users → base.py, engineers → chains.py)
4. **Focus on observability** with real implementation details for testing and visualzing in the prvoided full scale Streamlit app
5. **Protocol + Templates** flexible composition for different applications
6. **Clean examples** demonstrating the "companions as callables" pattern
7. **Practical guidance** for extending the framework
8. **Visual learning** - Sequence diagram up front, architecture docs linked

#### The goal: Show what makes Recursive Companion different and how to use it effectively.

---

## Built Through Collaboration

This framework emerged from intensive human-AI collaboration over 3 weeks:
- Solo developer working recursively with multiple LLMs
- Built using the very patterns it now enables  
- The architecture mirrors the discovery process itself

The rapid development was possible because the framework design emerged naturally from the recursive dialogue process—we were building what we were already doing. 
