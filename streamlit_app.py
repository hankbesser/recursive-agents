import streamlit as st
from pathlib import Path
from langchain.callbacks.base import BaseCallbackHandler


from recursive_companion import (
    GenericCompanion, 
    MarketingCompanion, 
    BugTriageCompanion, 
    StrategyCompanion,
    StreamlitGenericCompanion,
    StreamlitMarketingCompanion,
    StreamlitBugTriageCompanion,
    StreamlitStrategyCompanion
)

# Companion mapping for cleaner instantiation
COMPANION_MAP = {
    "generic": {
        "standard": GenericCompanion,
        "streamlit": StreamlitGenericCompanion
    },
    "marketing": {
        "standard": MarketingCompanion,
        "streamlit": StreamlitMarketingCompanion
    },
    "bug_triage": {
        "standard": BugTriageCompanion,
        "streamlit": StreamlitBugTriageCompanion
    },
    "strategy": {
        "standard": StrategyCompanion,
        "streamlit": StreamlitStrategyCompanion
    }
}

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

# Custom CSS to make text in expanders larger
#st.markdown("""
#<style>
    #.streamlit-expanderContent {
        #font-size: 20px !important;
    #}
#</style>
#""", unsafe_allow_html=True)

col_title, col_github = st.columns([4, 1])
with col_title:
    st.title("🔄 Recursive Companion Studio")
with col_github:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing to align with title
    st.markdown("[![GitHub](https://img.shields.io/badge/GitHub-Recursive%20Companion-blue?logo=github)](https://github.com/yourusername/recursive-companion)")

st.markdown("Watch the three-phase loop in action: draft, critique, and revision happening live • See how ideas deepen through recursive self-improvement")
st.markdown("<p style='color: #00ccff; font-size: 15px;'><strong>💡 Note:</strong> Click 'Apply Settings' in the sidebar to activate configuration changes • Settings changes will stop any analysis in progress</p>", unsafe_allow_html=True)

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
        'live_preview': True
    }

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    st.markdown("<p style='color: #00ccff; font-size: 13px;'>💡 Tip: Click » in top corner to collapse</p>", unsafe_allow_html=True)
    
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
        live_preview = st.checkbox("Live Preview", value=True, help="Show critique/revision process in real-time as it happens")
        # Disable show_critique if live_preview is on (live preview replaces it)
        show_critique = st.checkbox(
            "Show Critique Process", 
            value=True, 
            disabled=live_preview,
            help="Disabled when Live Preview is on" if live_preview else "Show the refinement process after analysis"
        )
        show_metrics = st.checkbox("Show Metrics", value=True)
        
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
            'show_critique': show_critique and not live_preview,  # Auto-disable if live preview is on
            'show_metrics': show_metrics,
            'live_preview': live_preview
        }
        st.success("✅ Settings applied!")
    
    # Show what settings will be used
    st.divider()
    st.markdown("<p style='color: #00ccff; font-size: 14px;'><strong>Settings for next analysis:</strong></p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Template Set: {st.session_state.applied_settings['selected_template']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Model: {st.session_state.applied_settings['model']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Temperature: {st.session_state.applied_settings['temperature']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Max Critique Loops: {st.session_state.applied_settings['max_loops']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Similarity Threshold: {st.session_state.applied_settings['similarity_threshold']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Show Critique Process: {'✓' if st.session_state.applied_settings['show_critique'] else '✗'}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Show Metrics: {'✓' if st.session_state.applied_settings['show_metrics'] else '✗'}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #00ccff; font-size: 14px;'>Live Preview: {'✓' if st.session_state.applied_settings['live_preview'] else '✗'}</p>", unsafe_allow_html=True)
    

# Main interface
col1, col2 = st.columns([1, 1])

with col1:
    # Input area
    st.markdown("##### Enter your problem or question:")
    user_input = st.text_area(
        "Input",  # Non-empty label required by Streamlit
        height=150,  # Taller box so text can wrap properly
        placeholder="Example: Our customer retention dropped 25% after the latest update. Support tickets mention confusion with the new interface. What's happening?",
        help="Press Ctrl+Enter (or Cmd+Enter on Mac) to analyze",
        label_visibility="collapsed"
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
                live_container = st.empty()  # Use st.empty() for dynamic updates!
            
            with st.spinner("Thinking..."):
                try:
                    # Select companion class based on settings
                    template_type = current_settings['selected_template']
                    companion_type = "streamlit" if current_settings['live_preview'] else "standard"
                    companion_class = COMPANION_MAP[template_type][companion_type]
                    
                    # Build kwargs for companion instantiation
                    companion_kwargs = {
                        'llm': current_settings['model'],
                        'temperature': current_settings['temperature'],
                        'max_loops': current_settings['max_loops'],
                        'similarity_threshold': current_settings['similarity_threshold'],
                        'return_transcript': True,
                        'clear_history': True
                    }
                    
                    # Add specific kwargs based on companion type
                    if companion_type == "streamlit":
                        companion_kwargs['progress_container'] = live_container
                    else:
                        companion_kwargs['verbose'] = False
                    
                    # Create companion instance
                    companion = companion_class(**companion_kwargs)
                    
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
                token_estimate = len(total_text) // 3.7
                st.metric("~Tokens Used", f"{token_estimate:,}")
            
            with metrics_col3:
                # Check if converged early
                converged = len(results['run_log']) < results['max_loops']
                st.metric("Early Exit", "Yes" if converged else "No")

with col2:
    # Template viewer
    st.markdown("#### 📄 Active System Templates and Protocol")
    
    template_tabs = st.tabs([    "**Initial** ",     "**Critique** ",     "**Revision** ",     "**Protocol** "])
    
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
    
    with template_tabs[3]:
        protocol_path = Path("templates/protocol_context.txt")
        if protocol_path.exists():
            st.code(protocol_path.read_text(), language="text")
        else:
            st.info("No protocol file found")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center;'>
    <span style='color: #00ccff;'>Built with Recursive Companion Framework | Templates are loaded from </span>
    <code style='background-color: #f0f2f6; padding: 2px 6px; border-radius: 3px; color: #ff6b6b;'>templates/</code>
    <span style='color: #00ccff;'> directory</span>
    </div>
    """, 
    unsafe_allow_html=True
)