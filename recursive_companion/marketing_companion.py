# companion/marketing_companion.py
"""
MarketingCompanion
------------------
Specialised lens for growth, funnel and audience-sentiment problems.

* Inherits the three-phase critique/revision loop, similarity early-exit,
  history handling and optional run-log from ``BaseCompanion``.
* Re-uses every generic prompt except **initial_sys**, which is replaced by
  ``templates/marketing_initial_sys.txt`` (merged via ``**GENERIC_TEMPLATES``).
* Sets ``MAX_LOOPS = 2`` so marketing narratives converge quickly.

Typical use
-----------
>>> agent = MarketingCompanion(llm, verbose=False)
>>> answer = agent.loop("Instagram engagement fell 30 %; why?")
"""

from .generic_companion import GENERIC_TEMPLATES    # <- plain dict
from core.chains import BaseCompanion, load

MARKETING_TEMPLATES = {
    **GENERIC_TEMPLATES, # bring all 5 keys
    "initial_sys": load("marketing_initial_sys").format(
        context=load("protocol_context")
    ),
}

class MarketingCompanion(BaseCompanion):
    TEMPLATES = MARKETING_TEMPLATES
    MAX_LOOPS = 2

    # Do subclasses need their own __init__ / super().__init__()?
    # They only need one when they must add extra constructor logic (i.e):

    # def __init__(self, llm, *, channel_weights=None, **kw):
        # super().__init__(llm, **kw)          # builds chains, sets history
        # self.channel_weights = channel_weights or {"email": 1, "social": 1}