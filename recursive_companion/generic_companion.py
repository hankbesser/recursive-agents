# generic_companion.py
"""
GenericCompanion
================
Domain-agnostic baseline implementation.

Purpose
-------
* Provides the **default** Strategic-Problem-Decomposition prompts
  (`generic_*_sys.txt`, `generic_*_user.txt`).
* Serves as the parent class many domain variants can inherit from,
  re-using the full 5-key template set and all runtime options.

Key Behaviours (inherited from *BaseCompanion*)
----------------------------------------------
✔ Three-phase **Initial → Critique → Revision** loop  
✔ **Similarity** early-exit (`SIM_THRESHOLD`)  
✔ **history** list for cross-call continuity  
✔ **run_log** capturing every inner iteration of the **most-recent call**  
  (always stored on the instance; also returned in a tuple **only** when
  `return_transcript=True`).  
        -Optional **tuple return** - `(final_answer, run_log)`  
✔ Toggleable **verbose** logging

Class-level Defaults
--------------------
* ``TEMPLATES``                - 5-key dict loaded from generic template files
* ``MAX_LOOPS``                - 3        (inner critique/revision passes)
* ``SIM_THRESHOLD``            - 0.98     (cosine similarity stop)
* ``CLEAR_HISTORY_AFTER_CALL`` - False    (keep conversation by default)
* ``RETURN_TRANSCRIPT``        - False    (single-string return by default)

Typical Usage
-------------
>>> from companion import GenericCompanion
>>> agent = GenericCompanion(llm="gpt-4o-mini", return_transcript=True)
>>> final, steps = agent.loop("We doubled staff but response time worsened—why?")
>>> print(final)            # refined answer string
>>> print(steps)            # same as agent.run_log
>>> print(agent.history)    # conversation across calls

Inheritance Pattern
-------------------
BaseCompanion
└── **GenericCompanion**                ← this class (domain-neutral)
    ├── MarketingCompanion              (overrides *only* ``initial_sys``)
    ├── BugTriageCompanion
    └── StrategyCompanion

Subclasses either:

* inherit directly from **GenericCompanion** and override the template keys
  they need, **or**
* merge ``GENERIC_TEMPLATES`` into a new dict if they inherit directly from
  *BaseCompanion*.

This keeps every variant tiny while preserving the complete prompt set.
"""

from core.chains import BaseCompanion, load

# ── template dictionary -------------------------------------------------
GENERIC_TEMPLATES = {
    # System prompts include the shared protocol_context.txt
    "initial_sys":  load("generic_initial_sys").format(context=load("protocol_context")),
    "critique_sys": load("generic_critique_sys").format(context=load("protocol_context")),
    "revision_sys": load("generic_revision_sys").format(context=load("protocol_context")),

    # User prompts need no context injection
    "critique_user": load("generic_critique_user"),
    "revision_user": load("generic_revision_user"),
}

# ── companion class -----------------------------------------------------
class GenericCompanion(BaseCompanion):
    """Default companion suitable for any problem domain."""
    TEMPLATES = GENERIC_TEMPLATES          # inherit all other defaults unchanged
