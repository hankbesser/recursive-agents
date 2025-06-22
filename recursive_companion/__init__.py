# companion/__init__.py
"""
Public API surface for the Recursive Companion package.

Most users should import classes directly from this package root:

    from companion import GenericCompaniom
    agent = GenericCompanion(llm)

If you later move or rename the implementation modules, only this file
needs updating—user code stays stable.
"""

# ---------------------------------------------------------------------
# Re-export the core engine (optional but often handy)
# ---------------------------------------------------------------------
from core.chains import BaseCompanion        

# ---------------------------------------------------------------------
# Re-export all concrete agents
# ---------------------------------------------------------------------
from .generic_companion import GenericCompanion                   
from .marketing_companion import MarketingCompanion     
from .bug_triage_companion import BugTriageCompanion     
from .strategy_companion import StrategyCompanion        

# ---------------------------------------------------------------------
# What `from companion import *` should expose
# ---------------------------------------------------------------------
__all__ = [
    "BaseCompanion",
    "GenericCompanion",
    "MarketingCompanion",
    "BugTriageCompanion",
    "StrategyCompanion",
]