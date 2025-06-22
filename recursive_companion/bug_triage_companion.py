# companion/bug_triage_companion.py
"""
BugTriageCompanion
------------------
Engineering-centric viewpoint that stresses reproducibility, environment
details and impact scope.

* Only overrides ``initial_sys`` (``templates/bug_initial_sys.txt``); the four
  generic critique/revision templates remain unchanged.
* Keeps the default ``MAX_LOOPS = 3`` to allow deeper technical iterations.
* All BaseCompanion inspection helpers (`history`, `run_log`, etc.) apply.

Example
-------
>>> triager = BugTriageCompanion(llm, similarity_threshold=0.97)
>>> report  = triager.loop("App crashes on photo upload for iOS 17")
"""

from .generic_companion import GENERIC_TEMPLATES    # <- plain dict
from core.chains import BaseCompanion, load

BUG_TRIAGE_TEMPLATES = {
    **GENERIC_TEMPLATES, # bring all 5 keys
    "initial_sys": load("bug_triage_initial_sys").format(
        context=load("protocol_context")
    ),
}

class BugTriageCompanion(BaseCompanion):
    TEMPLATES = BUG_TRIAGE_TEMPLATES
    MAX_LOOPS = 3