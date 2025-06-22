# strategy_companion.py
"""
StrategyCompanion
-----------------
Integrator that fuses multiple expert perspectives into one coherent action
plan.

* Overrides only ``initial_sys`` → ``templates/strategy_initial_sys.txt``.
* Lowers ``SIM_THRESHOLD`` slightly (0.97) to accept near-identical final
  drafts if perspectives already align.
* Ideal final step after MarketingCompanion + BugTriageCompanion analyses.

Quick demo
----------
>>> # --- multi-agent workflow ---------------------------------
>>> marketing_prompt = (
...     "Engagement on Instagram fell 35 % after our April campaign. "
...     "Analyse possible audience-side causes."
... )

>>> bug_prompt = (
...     "Mobile app crashes on photo upload for iOS 17.2 devices. "
...     "Summarise root-cause hypotheses from recent bug reports."
... )

>>> # 1) Run domain-specific companions
>>> marketing_report = MarketingCompanion(llm="gpt-4o-mini").loop(marketing_prompt)
>>> bug_report       = BugTriageCompanion(llm="gpt-4o-mini").loop(bug_prompt)

>>> # 2) Merge perspectives
>>> combined_views = (
...     f"### Marketing View\\n{marketing_report}\\n\\n"
...     f"### Engineering View\\n{bug_report}\\n\\n"
...     "Merge these perspectives and propose next actions."
... )

>>> # 3) Synthesise a unified strategy
>>> synth  = StrategyCompanion(llm="gpt-4o-mini", return_transcript=True)
>>> final, steps = synth.loop(combined_views)
>>> print(final)                               # polished cross-functional plan
>>> # print(synth.transcript_as_markdown())    # if you want the inner trail
"""

from .generic_companion import GENERIC_TEMPLATES    # <- plain dict
from core.chains import BaseCompanion, load


STRATEGY_TEMPLATES = {
    **GENERIC_TEMPLATES, # bring all 5 keys
    "initial_sys": load("strategy_initial_sys").format(context=load("protocol_context")),
}

class StrategyCompanion(BaseCompanion):
    """
    Integrates multiple expert perspectives into a coherent action plan.
    """
    TEMPLATES     = STRATEGY_TEMPLATES
    SIM_THRESHOLD = 0.97     # allow a bit more similarity before stopping
