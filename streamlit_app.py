import streamlit as st
from pathlib import Path
import json
import asyncio
from typing import Any, Dict, List
import threading
import time

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult

from recursive_companion import (
    GenericCompanion, 
    MarketingCompanion, 
    BugTriageCompanion, 
    StrategyCompanion
)

from core.streamlit_chains import (
    StreamlitGenericCompanion,
    StreamlitMarketingCompanion,
    StreamlitBugTriageCompanion,
    StreamlitStrategyCompanion
)

# Callback to capture streaming tokens
class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, container):
        self.container = container
        self.text = ""
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)

# Streamlit app
st.set_page_config(
    page_title="Recursive Companion Studio", 
    page_icon="🔄",
    layout="wide"
)

st.title("🔄 Recursive Companion Studio")
st.markdown("Watch AI agents critique and refine their own responses in real-time")

# Initialize session state for results persistence
if 'results' not in st.session_state:
    st.session_state.results = None
if 'last_input' not in st.session_state:
    st.session_state.last_input = ""
if 'last_settings' not in st.session_state:
    st.session_state.last_settings = {}
if 'applied_settings' not in st.session_state:
    st.session_state.applied_settings = {
        'model': 'gpt-4o-mini',
        'temperature': 0.7,
        'max_loops': 3,
        'similarity_threshold': 0.98,
        'selected_template': 'generic',
        'show_critique': True,
        'show_metrics': True,
        'live_preview': False
    }

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption("💡 Tip: Click » in top corner to collapse")
    
    # Use a form to prevent reruns while changing settings
    with st.form("config_form"):
        # Template selection - only show the built-in companions
        template_sets = ["generic", "marketing", "bug_triage", "strategy"]
        
        selected_template = st.selectbox(
            "Template Set",
            template_sets,
            help="Choose which companion type to use"
        )
        
        # Model settings
        model = st.selectbox(
            "Model",
            ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            help="Select the LLM model",
        )
        
        temperature = st.slider(
            "Temperature",
            0.0, 1.0, 0.7,
            help="Controls randomness in responses",
        )
        
        max_loops = st.slider(
            "Max Critique Loops",
            1, 5, 3,
            help="Maximum number of critique-revision cycles",
        )
        
        similarity_threshold = st.slider(
            "Similarity Threshold",
            0.90, 0.99, 0.98, 0.01,
            help="Stop when revisions are this similar",
        )
        
        # Display options
        show_critique = st.checkbox("Show Critique Process", value=True)
        show_metrics = st.checkbox("Show Metrics", value=True)
        live_preview = st.checkbox("Live Preview", value=False, help="Show critique/revision process in real-time as it happens")
        
        # Apply button
        apply_settings = st.form_submit_button("Apply Settings", type="secondary")
        
    # Update applied settings when button is clicked
    if apply_settings:
        st.session_state.applied_settings = {
            'model': model,
            'temperature': temperature,
            'max_loops': max_loops,
            'similarity_threshold': similarity_threshold,
            'selected_template': selected_template,
            'show_critique': show_critique,
            'show_metrics': show_metrics,
            'live_preview': live_preview
        }
        st.success("✅ Settings applied!")
    
    # Show what settings will be used
    st.divider()
    st.caption("**Settings for next analysis:**")
    st.caption(f"Template Set: {st.session_state.applied_settings['selected_template']}")
    st.caption(f"Model: {st.session_state.applied_settings['model']}")
    st.caption(f"Temperature: {st.session_state.applied_settings['temperature']}")
    st.caption(f"Max Critique Loops: {st.session_state.applied_settings['max_loops']}")
    st.caption(f"Similarity Threshold: {st.session_state.applied_settings['similarity_threshold']}")
    st.caption(f"Show Critique Process: {'✓' if st.session_state.applied_settings['show_critique'] else '✗'}")
    st.caption(f"Show Metrics: {'✓' if st.session_state.applied_settings['show_metrics'] else '✗'}")
    st.caption(f"Live Preview: {'✓' if st.session_state.applied_settings['live_preview'] else '✗'}")
    

# Main interface
col1, col2 = st.columns([2, 1])

with col1:
    # Input area
    user_input = st.text_area(
        "Enter your problem or question:",
        height=150,  # Taller box so text can wrap properly
        placeholder="Example: Our customer retention dropped 25% after the latest update. Support tickets mention confusion with the new interface. What's happening?",
        help="Press Ctrl+Enter (or Cmd+Enter on Mac) to analyze"
    )
    
    # Process button - only run analysis if it's a new input or settings changed
    # Use the APPLIED settings, not the form values
    current_settings = st.session_state.applied_settings
    
    if st.button("🚀 Analyze", type="primary", disabled=not user_input):
        # Run if: new input, no results yet, or settings changed
        if (user_input != st.session_state.last_input or 
            not st.session_state.results or
            current_settings != st.session_state.last_settings):
            
            # Create container for live preview if enabled
            live_container = None
            if current_settings['live_preview']:
                st.success("Analysis in progress...")
                live_expander = st.expander("🔄 Live Refinement Process", expanded=True)
                live_container = live_expander.container()
            
            with st.spinner("Thinking..."):
                try:
                    # Create companion with APPLIED settings
                    # Use Streamlit companions if live preview is enabled
                    if current_settings['live_preview']:
                        # Use Streamlit-enabled companions for live updates
                        if current_settings['selected_template'] == "generic":
                            companion = StreamlitGenericCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                clear_history=True,
                                progress_container=live_container  # Pass the container for live updates
                            )
                        elif current_settings['selected_template'] == "marketing":
                            companion = StreamlitMarketingCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                clear_history=True,
                                progress_container=live_container
                            )
                        elif current_settings['selected_template'] == "bug_triage":
                            companion = StreamlitBugTriageCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                clear_history=True,
                                progress_container=live_container
                            )
                        elif current_settings['selected_template'] == "strategy":
                            companion = StreamlitStrategyCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                clear_history=True,
                                progress_container=live_container
                            )
                    else:
                        # Use regular companions without live updates
                        if current_settings['selected_template'] == "generic":
                            companion = GenericCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                verbose=False,
                                clear_history=True
                            )
                        elif current_settings['selected_template'] == "marketing":
                            companion = MarketingCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                verbose=False,
                                clear_history=True
                            )
                        elif current_settings['selected_template'] == "bug_triage":
                            companion = BugTriageCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                verbose=False,
                                clear_history=True
                            )
                        elif current_settings['selected_template'] == "strategy":
                            companion = StrategyCompanion(
                                llm=current_settings['model'],
                                temperature=current_settings['temperature'],
                                max_loops=current_settings['max_loops'],
                                similarity_threshold=current_settings['similarity_threshold'],
                                return_transcript=True,
                                verbose=False,
                                clear_history=True
                            )
                    
                    # Run the analysis - always get transcript
                    final_answer, run_log = companion.loop(user_input)
                    
                    # Store results in session state
                    st.session_state.results = {
                        'final_answer': final_answer,
                        'run_log': run_log,
                        'max_loops': max_loops,
                        'user_input': user_input
                    }
                    st.session_state.last_input = user_input
                    st.session_state.last_settings = current_settings
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    # Display results from session state (persists across reruns)
    if 'results' in st.session_state and st.session_state.results:
        results = st.session_state.results
        
        st.success("Analysis complete!")
        
        # Final answer
        st.markdown("### 📋 Final Analysis")
        st.markdown(results['final_answer'])
        
        # Show critique process if enabled and not already shown via live preview
        if (st.session_state.applied_settings['show_critique'] and 
            results['run_log'] and 
            not st.session_state.applied_settings.get('live_preview', False)):
            with st.expander("🔄 Refinement Process", expanded=False):
                # Show initial draft once at the beginning
                if results['run_log']:
                    st.markdown("**Initial Draft**")
                    st.markdown("")  # Space between title and text
                    st.markdown(results['run_log'][0]["draft"])
                    st.markdown("---")
                
                # Show each iteration's critique and revision
                for i, step in enumerate(results['run_log'], 1):
                    is_last = (i == len(results['run_log']))
                    
                    st.markdown(f"**Critique {i}**")
                    st.markdown("")  # Space between title and text
                    st.markdown(step["critique"])
                    
                    # Only show revision if not the last iteration (to avoid redundancy with final answer)
                    if not is_last:
                        st.markdown("---")
                        st.markdown(f"**Revision {i}**")
                        st.markdown("")  # Space between title and text
                        st.markdown(step["revision"])
                    
                    # Add separator after each iteration (except the last)
                    if i < len(results['run_log']):
                        st.markdown("---")
        
        # Show metrics if enabled (check applied settings)
        if st.session_state.applied_settings['show_metrics']:
            st.markdown("### 📊 Metrics")
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            with metrics_col1:
                st.metric("Iterations", len(results['run_log']))
            
            with metrics_col2:
                # Calculate token estimate (rough)
                total_text = results['user_input'] + results['final_answer']
                for step in results['run_log']:
                    total_text += step.get("draft", "") + step.get("critique", "") + step.get("revision", "")
                token_estimate = len(total_text) // 4
                st.metric("~Tokens Used", f"{token_estimate:,}")
            
            with metrics_col3:
                # Check if converged early
                converged = len(results['run_log']) < results['max_loops']
                st.metric("Early Exit", "Yes" if converged else "No")

with col2:
    # Template viewer
    st.markdown("### 📄 Active Templates")
    
    template_tabs = st.tabs(["Initial", "Critique", "Revision"])
    
    with template_tabs[0]:
        initial_template = f"templates/{selected_template}_initial_sys.txt"
        if Path(initial_template).exists():
            st.code(Path(initial_template).read_text(), language="text")
        else:
            st.code(Path("templates/generic_initial_sys.txt").read_text(), language="text")
    
    with template_tabs[1]:
        critique_template = f"templates/{selected_template}_critique_sys.txt"
        if Path(critique_template).exists():
            st.code(Path(critique_template).read_text(), language="text")
        else:
            st.code(Path("templates/generic_critique_sys.txt").read_text(), language="text")
    
    with template_tabs[2]:
        revision_template = f"templates/{selected_template}_revision_sys.txt"
        if Path(revision_template).exists():
            st.code(Path(revision_template).read_text(), language="text")
        else:
            st.code(Path("templates/generic_revision_sys.txt").read_text(), language="text")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    Built with Recursive Companion Framework | 
    Templates are loaded from <code>templates/</code> directory
    </div>
    """, 
    unsafe_allow_html=True
)