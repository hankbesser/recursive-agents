# Recursive Companion 🔄

## A Meta-Framework for Self-Improving AI Agents

Recursive Companion implements a unique **three-phase iterative refinement architecture** that transforms how AI agents approach complex problems. Unlike traditional single-pass
systems, it discovers hidden problem structures through recursive decomposition and pattern emergence.

### Why Recursive Companion?

Most AI frameworks treat problems as static puzzles to solve. Recursive Companion recognizes that **problems contain hidden architectures** that only reveal themselves through
iteration. Each analysis phase creates conditions for deeper insight, ultimately compressing complex symptoms into their essential dynamics.


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
# Create new domains by overriding one template
LEGAL_TEMPLATES = build_templates(initial_sys="legal_initial_sys")
class LegalCompanion(BaseCompanion):
    TEMPLATES = LEGAL_TEMPLATES
    SIM_THRESHOLD = 0.99  # Legal requires higher precision
```
---
## 🧠 The Core Innovation: Strategic Decomposition Protocol

While others prompt-engineer, we've embedded a philosophical framework that guides agents through:

```text
PHASE 1: Initial Decomposition
↓ Map visible territory without premature patterns
PHASE 2: Pattern Compression
↓ Find where symptoms share hidden roots
PHASE 3: Structural Synthesis
↓ Let compressed patterns expand into implications
CONVERGENCE: Mathematical similarity says "stop"
```
This protocol (templates/protocol_context.txt) transforms every companion into a pattern-discovery engine. Problems know their own solutions—we just create conditions for revelation.

---
## 🏗️ Architecture: Clean Layers, Clear Purpose
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

- **Engineers** → core/chains.py (the mathematics of convergence)
- **Users** → recursive_companion/base.py (picking companions)
- **Prompt Engineers** → templates/ + template_load_utils.py
- **UI Developers** → streamlit.py (progress containers)

---
## 🎯 Technical Deep Dive

**The Engine** (core/chains.py)
```python
class BaseCompanion:
    """
    Three-phase critique/revision with mathematical convergence.
    No hand-waving—cosine similarity decides when insight emerges.
    """
```
Key Innovations:
- **Global embeddings client** for process-wide efficiency
- **Two convergence mechanisms**:
    - Cosine similarity > threshold (default 0.98)
    - Critique phrases ("no further improvements")
- **History injection** via MessagesPlaceholder
- **Callable pattern**: Instances behave like functions

Domain Specialization (Tuned for Purpose)

| Companion | Loops | Temperature | Similarity | Purpose                |
|-----------|-------|-------------|------------|------------------------|
| Marketing | 2     | 0.7         | 0.98       | Fast audience insights |
| BugTriage | 3     | 0.7         | 0.98       | Root cause depth       |
| Strategy  | 3     | 0.7         | 0.97       | Synthesis flexibility  |
| Generic   | 3     | 0.7         | 0.98       | Domain-agnostic        |

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
---
## 🔧 Production Features

#### Observability

- **Verbose mode**: See every phase of thinking
- **Transcript capture**: Full run_log for debugging
- **Standard logging**: Integration-ready

### Efficiency

- **Token optimization**: No system prompt in history
- **Smart caching**: Single embeddings client
- **Early exit**: Stop when converged, not exhausted

### Flexibility

- **Any OpenAI model**: "gpt-4o-mini", "gpt-4", custom endpoints
- **Configurable everything**: Per-instance overrides
- **Template hot-reload:** Change prompts without code

---
## 🚀 Quick Start

### Install
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
```

### Verify
```bash
python demos/quick_setup.py
```

### See multi-agent in action
```bash
python multi_agent_demos/multi_agent_demo_raw_rc.py
```

###  With LangGraph
```bash
python multi_agent_demos/multi_agent_langgraph_demo.py
```
---
## 📝 Creating Your Own Companion

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
## 💡 Why This Architecture Matters

1. **Mathematical Convergence > Arbitrary Limits**
    - Not "stop after 3 tries"
    - Stop when `cosine(draft[n-1], draft[n]) > 0.98`
2. **Companions as Callables = Composability**
- Works in Jupyter: 'agent("question")'
- Works in LangGraph: 'RunnableLambda(agent)'
- Works in APIs: 'return agent(request.prompt)'
3. **Templates as Data = Evolution Without Refactoring**
- Change prompts in production
- A/B test different protocols
- Domain experts can contribute without coding

---
## 🎓 Understanding the Magic

The power isn't only a modular/flexible code base—it's in the protocol. Read ```templates/protocol_context.txt``` to understand how we guide LLMs to:

- Treat problems as having "hidden architectures"
- Use iteration to create "conditions for emergence"
- Recognize when "compression precedes breakthrough"

This isn't mystical—it's a structured approach to recursive problem decomposition that consistently outperforms single-pass analysis.

---
## 📊 Benchmarks & Examples

See multi_agent_demos/ for complete examples:

- Raw RC: Simple, sequential, readable
- LangGraph: Parallel, traceable, production-scale

Both use identical companion objects. No refactoring needed.

---
*Built on the principle that true understanding emerges through iteration, and that the best frameworks disappear into your code.*

**License**

MIT

**Contributing**

PRs welcome! See our ```CONTRIBUTING.md```.

Special interest in:
- New domain templates
- Alternative embedding models for similarity
- Convergence visualization tools

This README inteded overall intentions:

1. **Three-level structure** mirrors the codebase organization
2. **Technical depth** with actual code snippets and architecture
3. **Clear separation** of who should look where
4. **Production focus** with real implementation details
5. **Philosophy + Mathematics** showing it's not just prompts
6. **Clean examples** demonstrating the "companions as callables" pattern
7. **Practical guidance** for extending the framework
