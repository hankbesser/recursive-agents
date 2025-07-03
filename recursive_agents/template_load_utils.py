# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# recursive_agents/template_load_utils.py
"""
Template loading utilities for the Recursive Agents framework.
================================================================

This module provides a modular way to compose template sets while
maintaining flexibility for customization.

The pattern: Most companions share generic critique/revision templates
but can override ANY template if needed.
"""

from pathlib import Path

# Use the same template directory as core.chains
TEMPL_DIR = Path(__file__).parent.parent / "templates"


def _load(name: str) -> str:
    """
    Read templates/<name>.txt (utf-8).
    
    This is a duplicate of core.chains.load() to avoid circular imports
    and keep this module independent.
    """
    return (TEMPL_DIR / f"{name}.txt").read_text()


def build_templates(**overrides):
    """
    Build a companion template set with optional overrides.
    
    By default, uses generic templates for all 5 keys. Pass keyword
    arguments to override specific templates.
    
    Examples:
        # Just override initial_sys (most common pattern)
        build_templates(initial_sys="marketing_initial_sys")
        
        # Override multiple templates
        build_templates(
            initial_sys="custom_initial_sys",
            critique_sys="custom_critique_sys"
        )
    
    Returns:
        Dict with all 5 required template keys, with protocol_context
        injected into system prompts.
    """
    # Load protocol context once
    protocol_context = _load("protocol_context")
    
    # Define defaults
    defaults = {
        "initial_sys": "generic_initial_sys",
        "critique_sys": "generic_critique_sys", 
        "revision_sys": "generic_revision_sys",
        "critique_user": "generic_critique_user",
        "revision_user": "generic_revision_user",
    }
    
    # Apply overrides
    template_names = {**defaults, **overrides}
    
    # Build final template dict -- adding the proctol to system templates
    # but you change to what ever you feel suited to how the protocol should
    # be progrigated thoughout the multiphase system
    templates = {}
    for key, template_name in template_names.items():
        content = _load(template_name)
        # Only system prompts get protocol context
        if key.endswith("_sys"):
            content = content.format(context=protocol_context)
        templates[key] = content
    
    return templates
