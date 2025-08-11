"""
Template Resources for MCP Exposure
===================================

This module handles automatic discovery of all templates in the templates directory
and exposes them as MCP resources with multiple access patterns. Each resource 
returns both content and metadata.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Use the same template directory as protocol.py
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

# Template metadata structure
@dataclass
class TemplateInfo:
    """Metadata for a discovered template."""
    filename: str
    domain: str
    phase: str  # initial, critique, revision
    type: str   # sys, user
    full_path: Path
    
    @property
    def uses_protocol(self) -> bool:
        """System templates use protocol injection."""
        return self.type == "sys"


class TemplateDiscovery:
    """Discovers and manages template files for MCP resource exposure."""
    
    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.template_dir = template_dir
        self.templates: Dict[str, TemplateInfo] = {}
        self._template_cache: Dict[str, Tuple[str, float]] = {}  # {path: (content, mtime)}
        self._discovered = False
        
    def discover_templates(self) -> Dict[str, TemplateInfo]:
        """Scan template directory and build metadata registry."""
        if self._discovered and self.templates:
            return self.templates
            
        self.templates.clear()
        
        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            return self.templates
            
        # Scan for all .txt files
        for template_file in self.template_dir.glob("*.txt"):
            if template_file.name == "protocol_context.txt":
                # Skip protocol - handled separately
                continue
                
            try:
                info = self._parse_template_filename(template_file)
                if info:
                    # Key format: domain/type/phase
                    key = f"{info.domain}/{info.type}/{info.phase}"
                    self.templates[key] = info
                    logger.debug(f"Discovered template: {key}")
            except Exception as e:
                logger.error(f"Error parsing template {template_file.name}: {e}")
                
        self._discovered = True
        logger.info(f"Discovered {len(self.templates)} templates")
        return self.templates
        
    def _parse_template_filename(self, file_path: Path) -> Optional[TemplateInfo]:
        """Parse template filename to extract metadata.
        
        Expected patterns:
        - generic_initial_sys.txt -> domain=generic, phase=initial, type=sys
        - marketing_initial_sys.txt -> domain=marketing, phase=initial, type=sys
        - generic_critique_user.txt -> domain=generic, phase=critique, type=user
        - bug_triage_initial_sys.txt -> domain=bug_triage, phase=initial, type=sys
        """
        filename = file_path.stem  # Remove .txt extension
        parts = filename.split('_')
        
        if len(parts) < 3:
            logger.warning(f"Unexpected template filename format: {file_path.name}")
            return None
            
        # Handle multi-word domains like bug_triage
        if len(parts) > 3:
            # Assume last two parts are phase and type
            type_part = parts[-1]
            phase = parts[-2]
            domain = '_'.join(parts[:-2])
        else:
            # Standard format
            domain = parts[0]
            phase = parts[1]
            type_part = parts[2]
        
        # Validate phase
        if phase not in ['initial', 'critique', 'revision']:
            logger.warning(f"Unknown phase in template: {file_path.name}")
            return None
            
        # Validate type
        if type_part not in ['sys', 'user']:
            logger.warning(f"Unknown type in template: {file_path.name}")
            return None
            
        return TemplateInfo(
            filename=file_path.name,
            domain=domain,
            phase=phase,
            type=type_part,
            full_path=file_path
        )
        
    def get_template_content(self, template_info: TemplateInfo) -> str:
        """Get template content with caching and hot-reload support."""
        path_str = str(template_info.full_path)
        
        try:
            mtime = template_info.full_path.stat().st_mtime
            cached = self._template_cache.get(path_str)
            
            if cached and cached[1] == mtime:
                return cached[0]
                
            # Read fresh content
            content = template_info.full_path.read_text(encoding="utf-8")
            self._template_cache[path_str] = (content, mtime)
            return content
            
        except Exception as e:
            logger.error(f"Error reading template {template_info.filename}: {e}")
            return f"Error loading template: {str(e)}"
            
    def get_domains(self) -> List[str]:
        """Get list of all discovered domains."""
        if not self._discovered:
            self.discover_templates()
        return sorted(set(t.domain for t in self.templates.values()))
        
    def get_templates_by_domain(self, domain: str) -> Dict[str, TemplateInfo]:
        """Get all templates for a specific domain."""
        if not self._discovered:
            self.discover_templates()
        return {k: v for k, v in self.templates.items() if v.domain == domain}
        
    def get_templates_by_phase(self, phase: str) -> Dict[str, TemplateInfo]:
        """Get all templates for a specific phase across all domains."""
        if not self._discovered:
            self.discover_templates()
        return {k: v for k, v in self.templates.items() if v.phase == phase}
        
    def get_templates_by_type(self, type_: str) -> Dict[str, TemplateInfo]:
        """Get all templates of a specific type across all domains."""
        if not self._discovered:
            self.discover_templates()
        return {k: v for k, v in self.templates.items() if v.type == type_}


# Singleton instance
template_discovery = TemplateDiscovery()


# ── Helper Functions ---------------------------------------------------------

def get_template_with_metadata(template_key: str) -> Dict[str, Any]:
    """Get template content with full metadata.
    
    Args:
        template_key: Key in format "domain/type/phase"
        
    Returns:
        Dict containing content and metadata
    """
    templates = template_discovery.discover_templates()
    
    if template_key not in templates:
        raise ValueError(f"Template not found: {template_key}")
        
    template_info = templates[template_key]
    
    # Get content with caching
    content = template_discovery.get_template_content(template_info)
    
    # Get last modified time
    try:
        mtime = template_info.full_path.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime).isoformat()
    except Exception:
        last_modified = None
    
    return {
        "content": content,
        "metadata": {
            "uses_protocol": template_info.uses_protocol,
            "domain": template_info.domain,
            "phase": template_info.phase,
            "type": template_info.type,
            "last_modified": last_modified,
            "filename": template_info.filename,
            "key": template_key
        }
    }


# ── MCP Resource Functions ---------------------------------------------------

async def resource_template_by_path(domain: str, type: str, phase: str) -> Dict[str, Any]:
    """Access template by full path: domain/type/phase."""
    key = f"{domain}/{type}/{phase}"
    return get_template_with_metadata(key)


async def resource_templates_by_phase(phase: str, type: str) -> Dict[str, Any]:
    """Get all templates for a specific phase and type across domains."""
    templates = template_discovery.get_templates_by_phase(phase)
    results = {}
    
    for key, template_info in templates.items():
        if template_info.type == type:
            results[template_info.domain] = get_template_with_metadata(key)
    
    return {
        "query": {
            "phase": phase,
            "type": type
        },
        "templates": results,
        "count": len(results)
    }


async def resource_templates_by_domain(domain: str) -> Dict[str, Any]:
    """Get all templates for a specific domain."""
    templates = template_discovery.get_templates_by_domain(domain)
    results = {}
    
    for key, template_info in templates.items():
        # Organize by phase/type
        phase_type = f"{template_info.phase}/{template_info.type}"
        results[phase_type] = get_template_with_metadata(key)
    
    return {
        "query": {
            "domain": domain
        },
        "templates": results,
        "count": len(results)
    }


async def resource_all_templates() -> Dict[str, Any]:
    """Get all templates with metadata."""
    templates = template_discovery.discover_templates()
    results = {}
    
    for key in templates:
        results[key] = get_template_with_metadata(key)
    
    return {
        "templates": results,
        "count": len(results),
        "domains": template_discovery.get_domains()
    }


async def resource_template_domains() -> Dict[str, Any]:
    """List all available template domains."""
    domains = template_discovery.get_domains()
    
    # Get count of templates per domain
    domain_counts = {}
    for domain in domains:
        templates = template_discovery.get_templates_by_domain(domain)
        domain_counts[domain] = len(templates)
    
    return {
        "domains": domains,
        "counts": domain_counts,
        "total": len(domains)
    }