# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Henry Besser]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

# core/chains.py
"""
Core plumbing for all Companion subclasses
------------------------------------------

* cosine(a:str, b:str) → float
    Cached OpenAI-embedding cosine similarity.  Used to decide whether two
    successive revisions are “close enough” to stop looping early.

* build_chains(t:dict[str,str], llm:ChatOpenAI)
    Construct the **Init → Critique → Revision** runnables from a 5-key
    template dict.  Injects ``MessagesPlaceholder("history")``.

* BaseCompanion
    ├─ __init__(llm: str | ChatOpenAI | None = None,
    │           *,
    │           templates:dict[str,str] |       None = None,
    │           similarity_threshold:float |    None = None,
    │           max_loops:int | None          = None,
    │           temperature:float | None      = None,
    │           verbose:bool                  = False,
    │           clear_history:bool | None     = None,
    │           return_transcript:bool        = False,
    │           **llm_kwargs)
    │      · Builds an internal ``ChatOpenAI`` *if* caller passes a model-name
    │        string (no import needed in user code).
    │      · Creates ``history`` & ``run_log`` containers.
    │      · Merges caller kwargs with class-level defaults.
    │      · Builds the three chains via *build_chains()*.
    │
    ├─ loop(user_input:str)
    │      Returns **str**         (final draft)         when *return_transcript=False*
    │           or **(str, list)** (final, run_log)      when *return_transcript=True*
    │      · Performs the three-phase loop ≤ max_loops
    │      · similarity / empty-critique early-exit
    │      · Appends (Human, AI) messages to ``history``
    │      · Stores each {draft, critique, revision} dict in ``run_log``
    │      · Auto-clears history if ``self.clear_history`` is *True*
    │
    ├─ transcript_as_markdown() → str
    │      Nicely formatted view of ``run_log`` for notebooks / logs.
    │
    └─ Public instance attributes
           · history             list[HumanMessage|AIMessage]   (cross-call)
           · run_log             list[dict]  (inner iterations, last call)
           · sim_thresh          float       effective similarity threshold
           · max_loops           int         effective loop cap
           · temperature         float       effective sampling temperature
           · clear_history       bool        auto-wipe flag in effect
           · verbose             bool        debug logging flag

Design notes
============
* Templates live in ``templates/`` as text files.
* Subclasses set TEMPLATES class attribute (typically using build_templates() 
  from template_load_utils.py for DRY template composition).
* All debug output is gated by ``verbose`` OR standard logging levels.
* No system prompts are stored in history; token cost stays minimal.
"""

from typing import Dict, Any, List, Union, Optional
from numpy import dot
from numpy.linalg import norm
import logging

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

def cosine_from_embeddings(va: List[float], vb: List[float]) -> float:
    """Compute cosine similarity from pre-computed embeddings."""
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
class BaseCompanion:
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
        verbose: bool = False,
        embedding_model=None,
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

        self._emb = embedding_model or OpenAIEmbeddings()
        self.return_transcript = return_transcript
        self.verbose = verbose
        if self.verbose:                          # minimal logger setup
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(levelname)s | %(message)s"
            )
            # Suppress noisy httpx debug logs
            logging.getLogger("httpx").setLevel(logging.WARNING)

    # ---------- main recursive loop -----------------------------------
    def loop(self, user_input: str) ->  str | tuple[str, list]:
        if self.verbose:
            logging.debug("USER INPUT:\n%s", user_input.strip())
        
        # Note: That keeps run_log scoped to one outer call instead of accumulating across multiple. 
        # If you like the cumulative behaviour, skip this line.  
        self.run_log.clear()  # ← start fresh for this call
        
        # 1. initial draft
        draft = self.init_chain.invoke(
            {"user_input": user_input, "history": self.history}
        ).content
        
        if self.verbose:
            logging.debug("INITIAL DRAFT:\n%s\n", draft.strip())
        
        prev: str | None      = None          # previous draft text
        prev_emb: list | None = None          # previous embedding (starts empty)
        # 2. critique / revision cycles
        for i in range(1, self.max_loops + 1):
            critique = self.crit_chain.invoke(
                {"user_input": user_input, "draft": draft}
            ).content
            if self.verbose:
                logging.debug("CRITIQUE #%d:\n%s\n", i, critique.strip())

            # simple phrase-based early exit?
            if any(p in critique.lower() for p in ("no further improvements", "minimal revisions")):
                self.run_log.append({"draft": draft, "critique": critique, "revision": draft})
                if self.verbose:
                    logging.debug("Early-exit phrase detected.")
                break

            # revision
            revised = self.rev_chain.invoke(
                {"user_input": user_input, "draft": draft, "critique": critique}
            ).content

            # similarity check (embed once) - Compute similarity (only if we have a previous draft)
            if prev is None:
                sim = None
            else:
                if prev_emb is None:   # cache once
                    prev_emb = self._emb.embed_query(prev)
                cur_emb = self._emb.embed_query(revised)
                sim     = cosine_from_embeddings(prev_emb, cur_emb)

            if self.verbose:
                sim_display = sim if sim is not None else 0
                logging.debug("REVISION #%d (cosine=%.3f):\n%s\n", i, sim_display, revised.strip())
            
            # Similarity early-exit test (no extra row inside)
            if sim is not None and sim >= self.similarity_threshold:
                # 1) record this converging turn
                # 2) LOG FIRST — keep before/after contrast
                self.run_log.append({
                "draft":    draft,     # v n-1
                "critique": critique,  # critique on v n-1
                "revision": revised    # v n  (final)
                })
                if self.verbose:
                    logging.debug("Similarity threshold reached (%.2f).", self.similarity_threshold)                

                
                # update cached state *after* logging
                # update for final return
                prev = revised      # Cache the final text # won't be used again (since you're breaking), it's good practice to keep all state variables consistent
                draft = revised     # So caller sees final text  
                prev_emb = cur_emb  # Cache the final embedding  # won't be used again (since you're breaking), it's good practice to keep all state variables consistent
                break # exit loop
                
            # not converged → prepare for next round
            self.run_log.append({"draft": draft, "critique": critique, "revision": revised})
            prev = draft           # store current draft for next comparison
            if 'cur_emb' in locals():  # only cache if we computed it
                prev_emb = cur_emb      # cache embedding for next comparison    
            draft = revised        # update draft for next iteration

        # 3. update history & return
        self.history.extend([HumanMessage(user_input), AIMessage(draft)])
                
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
        
        if self.run_log:
            # Initial draft (from first iteration)
            out.append("\n" +"-" * 80 + "\n") 
            out.append("## Initial Draft")
            out.append("\n" +"-" * 80 + "\n") 
            out.append(self.run_log[0]["draft"])
            
            # Iterations (all but last)
            for idx, step in enumerate(self.run_log[:-1], 1):
                out.append(f"## Iteration {idx}")
                out.append("\n" + "-" * 80 + "\n")
                
                out.append(f"### Critique {idx}")
                out.append("\n" + "-" * 80 + "\n")
                out.append(step["critique"])
                
                out.append("\n" + f"### Revision {idx}")
                out.append("\n" + "-" * 80 + "\n")
                out.append(step["revision"])
              
            
            # Last iteration (shows critique but labels revision as final answer)
            if len(self.run_log) > 0:
                last_step = self.run_log[-1]
                out.append(f"## Iteration {len(self.run_log)}")
                out.append("\n" +"-" * 80 + "\n") 
                
                out.append(f"### Critique {len(self.run_log)}")
                out.append("\n" +"-" * 80 + "\n") 
                out.append(last_step["critique"])
                
                out.append("### Final Answer")
                out.append("\n" +"-" * 80 + "\n") 
                out.append(last_step["revision"])
        
        return "\n".join(out)


