# core/streamlit_chains.py
"""
Streamlit-specific version of chains.py with live update capabilities
---------------------------------------------------------------------

Same as core/chains.py but the loop() method emits real-time updates
to a Streamlit container if provided. See core/chains.py for detailed
documentation of the core algorithm.

The only difference is the addition of progress_container parameter
and live UI updates during the critique/revision loop.
"""

from typing import Dict, Any, List, Union, Optional
from numpy import dot
from numpy.linalg import norm
import streamlit as st

from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings # ChatOpenAI can stay internl!
from langchain_core.messages import HumanMessage, AIMessage

# ---------------------------------------------------------------------
# ❶ Global embeddings + cosine helper
# ---------------------------------------------------------------------
_emb = OpenAIEmbeddings()          # single process-wide client

def cosine(a: str, b: str) -> float:
    va, vb = _emb.embed_query(a), _emb.embed_query(b)
    return dot(va, vb) / (norm(va) * norm(vb))

# ---------------------------------------------------------------------
# ❷ Build three chains from template dict + LLM
# ---------------------------------------------------------------------
def build_chains(t: Dict[str, str], llm: ChatOpenAI):
    init_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(t["initial_sys"]),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{user_input}"),
    ])
    crit_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(t["critique_sys"]),
        HumanMessagePromptTemplate.from_template(t["critique_user"]),
    ])
    rev_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(t["revision_sys"]),
        HumanMessagePromptTemplate.from_template(t["revision_user"]),
    ])

    return init_prompt | llm, crit_prompt | llm, rev_prompt | llm

# ---------------------------------------------------------------------
# ❸ BaseCompanion
# ---------------------------------------------------------------------
class StreamlitBaseCompanion:
    """
    Three-phase critique / revision agent with optional early-exit and history.
    Subclasses override TEMPLATES (and optionally class defaults).
    """
    # ---------- class-level defaults (overridable in subclass) --------
    TEMPLATES: Dict[str, str] = {}
    MODEL_NAME: str = "gpt-4o-mini"
    DEFAULT_TEMPERATURE = 0.7                # sensible mid-range
    SIM_THRESHOLD: float = 0.98
    MAX_LOOPS: int = 3
    CLEAR_HISTORY_AFTER_CALL: bool = False   # subclass can override

    # ---------- constructor ------------------------------------------
    def __init__(
        self,
        llm: Optional[Union[str, ChatOpenAI]] = None,
        *,
        templates: Dict[str, str] | None = None,
        temperature: float | None = None,         
        similarity_threshold: float | None = None,
        max_loops: int | None = None,
        clear_history: bool | None = None,
        return_transcript: bool = False,
        progress_container = None,  # Streamlit container for live updates
        **llm_kwargs: Any, # passthrough                  
    ):
        # merge subclass templates with caller overrides
        merged = {**self.TEMPLATES, **(templates or {})}

        # auto-instantiate if needed
        # ── 1. build / validate the LLM object ──────────────────────────────
        if isinstance(llm, ChatOpenAI):
            # caller handed us a fully-configured LLM → just use it
            self.llm = llm
        else:
            # we must build the LLM ourselves
            model_name = llm or self.MODEL_NAME    # str or fallback
            temp       = temperature if temperature is not None else self.DEFAULT_TEMPERATURE
            self.llm = ChatOpenAI(
                model_name=model_name,
                temperature=temp,
                **llm_kwargs          # forwards anything extra
            )

        # build chains
        self.init_chain, self.crit_chain, self.rev_chain = build_chains(merged, self.llm)

        # instance-level parameters (fall back to class constants)
        self.similarity_threshold: float = (
            similarity_threshold if similarity_threshold is not None else self.SIM_THRESHOLD
        )
        self.max_loops: int = (
            max_loops if max_loops is not None else self.MAX_LOOPS
        )

        self.clear_history = (
            clear_history if clear_history is not None
            else self.CLEAR_HISTORY_AFTER_CALL
        )
        # conversation history (per instance)
        self.history: List[Any] = []     # list[HumanMessage | AIMessage]
        self.run_log: list[dict[str, str]] = []   # stores per-iteration details

        self.return_transcript = return_transcript
        self.progress_container = progress_container  # Store the Streamlit container

    # ---------- main recursive loop -----------------------------------
    def loop(self, user_input: str) ->  str | tuple[str, list]:
        # Note: That keeps run_log scoped to one outer call instead of accumulating across multiple. 
        # If you like the cumulative behaviour, skip this line.  
        self.run_log.clear()  # ← start fresh for this call
        
        # Live update: Show user input if container provided
        if self.progress_container:
            with self.progress_container:
                st.markdown("**Processing your input...**")
                st.markdown(f"_{user_input}_")
                st.markdown("---")
        
        # 1. initial draft
        draft = self.init_chain.invoke(
            {"user_input": user_input, "history": self.history}
        ).content
        
        # Live update: Show initial draft
        if self.progress_container:
            with self.progress_container:
                st.markdown("**Initial Draft**")
                st.markdown(draft)
                st.markdown("---")
        
        prev = None
        # 2. critique / revision cycles
        for i in range(1, self.max_loops + 1):
            critique = self.crit_chain.invoke(
                {"user_input": user_input, "draft": draft}
            ).content
            
            # Live update: Show critique
            if self.progress_container:
                with self.progress_container:
                    st.markdown(f"**Critique {i}**")
                    st.markdown(critique)
                    st.markdown("---")

            # simple phrase-based early exit?
            if any(p in critique.lower() for p in ("no further improvements", "minimal revisions")):
                self.run_log.append({"draft": draft, "critique": critique, "revision": draft})
                if self.progress_container:
                    with self.progress_container:
                        st.info("✓ Early exit: No further improvements needed")
                break

            revised = self.rev_chain.invoke(
                {"user_input": user_input, "draft": draft, "critique": critique}
            ).content
            
            # Live update: Show revision
            if self.progress_container:
                with self.progress_container:
                    st.markdown(f"**Revision {i}**")
                    st.markdown(revised)
                    if prev:
                        sim = cosine(prev, revised)
                        st.caption(f"_Similarity to previous: {sim:.3f}_")
                    st.markdown("---")

            # similarity early exit?
            if prev and cosine(prev, revised) > self.similarity_threshold:
                self.run_log.append({"draft": draft, "critique": critique, "revision": revised})
                if self.progress_container:
                    with self.progress_container:
                        st.success(f"✓ Converged: Similarity threshold reached ({self.similarity_threshold:.2f})")
                break

            self.run_log.append({"draft": draft, "critique": critique, "revision": revised})
            prev, draft = draft, revised

        # 3. update history & return
        self.history.extend([HumanMessage(user_input), AIMessage(draft)])
        
        # Live update: Show final result
        if self.progress_container:
            with self.progress_container:
                st.success("✓ Analysis complete!")
                st.markdown("**Final Answer**")
                st.markdown(draft)
                
        if self.clear_history:
            #kept = self.history.copy()  # optional: return copy to caller
            self.history.clear()
            # choose whether to return run_log
            return (draft, self.run_log) if self.return_transcript else draft
            
        # ---Honour return_transcript flag ---
        if self.return_transcript:
            return draft, self.run_log      # tuple: (final answer, inner steps)
            
        return draft                # or (draft, kept) if you want keep self.history.copy()
    
        # two lines - Adding just one dunder to BaseCompanion so every 
        # subclass automatically behaves like a function.
        # Nothing else changes; loop() is still the full three-phase engine.
        # (If you prefer not to touch the base class, you can add __call__ = loop in each subclass.)
    def __call__(self, user_input: str):
        """Alias so a Companion instance is itself a callable."""
        return self.loop(user_input)
    
    
    def transcript_as_markdown(self) -> str:
        """Pretty-print the last run for logs or UI."""
        out = []
        for idx, step in enumerate(self.run_log, 1):
            out.append(f"### Iteration {idx}")
            out.append("**Draft**\n\n"     + step["draft"])
            out.append("\n**Critique**\n\n" + step["critique"])
            out.append("\n**Revision**\n\n" + step["revision"])
            out.append("\n---\n")
        return "\n".join(out)