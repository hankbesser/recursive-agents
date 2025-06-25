# Recursive Companion 🔄

A framework for building specialized AI agents that critique and improve their own responses. Create domain experts in minutes, not days.

## What Makes This Different

**Build Any Expert Domain**  
Write one template file. Get a fully functional agent with critique-revision capabilities.

**True Modularity**  
System templates (agent identity), user templates (task structure), and protocols (reasoning patterns) compose independently. Change one without touching others.

**Works Everywhere**  
Companions are callables. Use them standalone, in web APIs, with LangGraph, in Jupyter notebooks - they adapt to your architecture, not the other way around.

**See Everything**  
Every agent tracks its complete revision history. Debug with real data. Understand decisions. No black boxes.

## Quick Start

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...

# Run included Streamlit app
streamlit run streamlit_app.py
```

You get a full interactive application. Select any companion, watch the critique-revision cycles live, export results.

## Creating New Companions

```python
# 1. Write your domain template (templates/medical_initial_sys.txt)
You are a Medical Analysis Companion. Focus on diagnostic reasoning 
and evidence-based recommendations.
{context}

# 2. Create the companion
class MedicalCompanion(BaseCompanion):
    TEMPLATES = build_templates(initial_sys="medical_initial_sys")

# 3. Use it
med = MedicalCompanion()
analysis = med("Patient presents with recurring symptoms...")
```

That's it. Your medical expert inherits the full critique-revision engine.

## The Template System

The `build_templates()` utility gives you fine-grained control:

```python
# Override just what you need
build_templates(initial_sys="legal_initial_sys")  # New domain, keep everything else

# Mix protocols and templates
build_templates(
    initial_sys="creative_initial_sys",
    critique_sys="strict_critique_sys"
)

# Skip protocols for baseline testing
build_templates(skip_protocol=True)
```

Templates compose from:
- **Protocols**: Strategic reasoning frameworks
- **System prompts**: Agent identity and expertise  
- **User prompts**: Task structure and formatting

Change any layer independently.

## Real Usage Examples

**Multi-Perspective Analysis**
```python
problem = "Product launch failed - customers confused by features"

# Each companion brings domain expertise
marketing = MarketingCompanion()
product = StrategyCompanion()
support = GenericCompanion()

# Analyze from each perspective
market_view = marketing(problem)
product_view = product(problem)
support_view = support(problem)

# Companions remain inspectable
print(f"Marketing refined answer {len(marketing.run_log)} times")
```

**API Integration**
```python
@app.post("/analyze")
def analyze(request):
    agent = BugTriageCompanion()
    result = agent(request.bug_report)
    
    return {
        "analysis": result,
        "iterations": len(agent.run_log),
        "confidence": check_completion_quality(agent.run_log)
    }
```

**Parallel Processing with LangGraph**
```python
# Companions work as graph nodes without modification
from langchain.runnables import RunnableLambda

mkt_node = RunnableLambda(MarketingCompanion())
eng_node = RunnableLambda(BugTriageCompanion())

# Full inspection still available after graph execution
```

## Architecture

```
recursive_companion/
├── base.py                 # Example companions
├── streamlit.py           # UI-enabled versions  
└── template_load_utils.py # Template composition logic

core/
└── chains.py              # The engine: 3-phase loop implementation

templates/
├── protocol_context.txt   # Strategic decomposition protocol
└── *.txt                  # Domain and phase templates
```

The engine builds three LangChain chains that cycle until quality stabilizes (measured by embedding similarity) or critique indicates completion.

## Included Examples

- **Full Streamlit App**: Interactive UI with live updates
- **Multi-Agent Demo**: Orchestrating multiple perspectives
- **LangGraph Integration**: Parallel execution patterns
- **Quick Setup**: Minimal working example

## Why This Matters

Traditional AI frameworks give you outputs. Recursive Companion gives you understanding.

Every decision is traceable. Every revision is logged. Every agent explains itself.

Build trustworthy AI systems that show their work.

## Contributing

PRs welcome for:
- New domain templates
- UI enhancements
- Alternative embedding models

## License

MIT