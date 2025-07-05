import sys
import os
from unittest.mock import MagicMock, AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Test setup utilities
# ---------------------------------------------------------------------------
# The MCP code lives in a folder with a hyphen.  We extend ``sys.path`` and
# alias the ``core`` package so the imports inside that module resolve
# correctly without installing optional dependencies like ``streamlit``.
sys.modules.setdefault("streamlit", MagicMock())
sys.path.insert(0, ".")
os.environ.setdefault("OPENAI_API_KEY", "test")

import importlib.util
import core
import core.chains  # required before aliasing

CORE_MCP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "recursive-agents-mcp", "core"))
sys.modules["recursive_agents.core"] = core
sys.modules["recursive_agents.core.chains"] = core.chains

# Manually load the MCP modules from their file paths
data_tools_path = os.path.join(CORE_MCP_PATH, "data_tools.py")
spec_dt = importlib.util.spec_from_file_location("core.data_tools", data_tools_path)
data_tools_mod = importlib.util.module_from_spec(spec_dt)
spec_dt.loader.exec_module(data_tools_mod)
sys.modules["core.data_tools"] = data_tools_mod

mcp_path = os.path.join(CORE_MCP_PATH, "mcp_aware_chains.py")
spec_mcp = importlib.util.spec_from_file_location("mcp_aware_chains", mcp_path)
mcp_mod = importlib.util.module_from_spec(spec_mcp)
spec_mcp.loader.exec_module(mcp_mod)
MCPAwareCompanion = mcp_mod.MCPAwareCompanion
from langchain_core.messages import AIMessage
from recursive_agents.template_load_utils import build_templates

class FakeEmbeddings:
    def embed_query(self, text: str):
        return [0.0]

class DummyChain:
    def __init__(self, text):
        self.text = text
    def invoke(self, *_args, **_kwargs):
        return AIMessage(content=self.text)

@pytest.mark.asyncio
async def test_mcp_loop_returns_answer_without_tools():
    templates = build_templates()
    comp = MCPAwareCompanion(
        use_external_tools=False,
        return_transcript=True,
        max_loops=1,
        embedding_model=FakeEmbeddings(),
        templates=templates,
    )
    comp.init_chain = DummyChain("draft")
    comp.crit_chain = DummyChain("critique")
    comp.rev_chain = DummyChain("revision")

    result, log = await comp.mcp_aware_loop("test")
    assert result == "revision"
    assert log[-1]["revision"] == "revision"

@pytest.mark.asyncio
async def test_mcp_loop_includes_tool_results_in_revision():
    templates = build_templates()
    comp = MCPAwareCompanion(
        use_external_tools=True,
        return_transcript=True,
        max_loops=1,
        embedding_model=FakeEmbeddings(),
        templates=templates,
    )
    comp.init_chain = DummyChain("draft")
    critique = (
        'Need data.\n[MCP_NEED: tool_type="web_search", query="cats", reason="context"]'
    )
    comp.crit_chain = DummyChain(critique)

    def fake_rev(inp):
        return f"REVISION: {inp['critique']}"

    class RevChain:
        def invoke(self, inp):
            return AIMessage(content=fake_rev(inp))
    comp.rev_chain = RevChain()
    comp.data_tools.execute_tool = AsyncMock(return_value="MOCK RESULTS")

    result, log = await comp.mcp_aware_loop("test")
    assert "MOCK RESULTS" in log[0]["revision"]
