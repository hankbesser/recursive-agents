# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# recursive_agents/__init__.py
"""
Public API surface for the Recursive Agents package.

Most users should import classes directly from this package root:

    from recursive_agents import GenericCompanion
    agent = GenericCompanion(llm="gpt-4o-mini")
    answer = agent("Analyze this problem...")

With new modular structure, companions are organized by UI framework:
    - base.py: Standard companions without UI integration
    - streamlit.py: Streamlit-enabled companions with live updates

If you later move or rename the implementation modules, only this file
needs updating—user code stays stable.
"""

# ---------------------------------------------------------------------
# Re-export the core engine (optional but often handy)
# ---------------------------------------------------------------------
from core.chains import BaseCompanion        

# ---------------------------------------------------------------------
# Re-export all concrete agents from base.py
# ---------------------------------------------------------------------
from .base import (
    GenericCompanion,
    MarketingCompanion,
    BugTriageCompanion,
    StrategyCompanion,
)

# ---------------------------------------------------------------------
# Re-export Streamlit-enabled agents from streamlit.py
# ---------------------------------------------------------------------
from .streamlit import (
    StreamlitGenericCompanion,
    StreamlitMarketingCompanion,
    StreamlitBugTriageCompanion,
    StreamlitStrategyCompanion,
)

# ---------------------------------------------------------------------
# What `from recursive_agents import *` should expose
# ---------------------------------------------------------------------
__all__ = [
    # Core
    "BaseCompanion",
    # Standard companions
    "GenericCompanion",
    "MarketingCompanion",
    "BugTriageCompanion",
    "StrategyCompanion",
    # Streamlit companions
    "StreamlitGenericCompanion",
    "StreamlitMarketingCompanion",
    "StreamlitBugTriageCompanion",
    "StreamlitStrategyCompanion",
]
