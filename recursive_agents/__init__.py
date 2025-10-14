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
# Re-export Streamlit-enabled agents from streamlit.py if streamlit is available
# ---------------------------------------------------------------------

try:
    # Attempt to import Streamlit-related modules
    from .streamlit import (
        StreamlitGenericCompanion,  # noqa: F401
        StreamlitMarketingCompanion,  # noqa: F401
        StreamlitBugTriageCompanion,  # noqa: F401
        StreamlitStrategyCompanion,  # noqa: F401
    )
    # You might want to define a flag indicating availability of Streamlit companions,
    # so that other parts of your code can check this flag to conditionally use them. 
    # This is especially useful in larger applications where you want to know
    # which optional modules are available, if needed elsewhere.
    STREAMLIT_AVAILABLE = True

except ImportError:
    # Handle the case where the 'streamlit' package is not installed.
    # The classes won't be available, but the program won't crash.
    # You can optionally log a message or define placeholder variables.
    print("Warning: Streamlit companions are unavailable. Install 'streamlit' to use them.")

    # Define dummy/placeholder variables for the classes if they need to exist
    # (e.g., if code later checks for their existence), though often not needed.
    # Example:
    # StreamlitGenericCompanion = None
    STREAMLIT_AVAILABLE = False
# ---------------------------------------------------------------------
# What `from recursive_agents import *` should expose
# ---------------------------------------------------------------------
# Core and standard companions are always available
__all__ = [
    # Core
    "BaseCompanion",
    # Standard companions
    "GenericCompanion",
    "MarketingCompanion",
    "BugTriageCompanion",
    "StrategyCompanion",
]

# Conditionally extend __all__ ONLY if the imports succeeded
if STREAMLIT_AVAILABLE:  # Assuming you defined this flag in the try block
    __all__.extend(
        [
            # Streamlit companions
            "StreamlitGenericCompanion",
            "StreamlitMarketingCompanion",
            "StreamlitBugTriageCompanion",
            "StreamlitStrategyCompanion",
        ]
    )
