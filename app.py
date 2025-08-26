#!/usr/bin/env python3
"""
AI Debate Club - Streamlit Web Interface

A user-friendly web interface for the AI Debate Club multi-agent system.
Features two main tabs:
1. Orchestrator Report - Professional debate report
2. Conversation UI - Messenger-style chat interface
"""

import streamlit as st
import asyncio
import os
from datetime import datetime

# Import from our debate_club module
from debate_club import (
    setup_openai_client, 
    create_pro_agent, 
    create_con_agent,
    create_tool_from_agent,
    create_orchestrator_agent,
    verbose_run_final
)

# Import personas
from personas import get_persona_names, get_persona_by_display_name

# =============================================================================
# STREAMLIT PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="🎭 AI Debate Club",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for messenger-style UI
st.markdown("""
<style>
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #f8f9fa;
    }
    
    .pro-message {
        background-color: #dcf8c6;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 15px 15px 5px 15px;
        margin-left: 0;
        margin-right: 20%;
        border-left: 4px solid #4CAF50;
    }
    
    .con-message {
        background-color: #f1f1f1;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 15px 15px 15px 5px;
        margin-left: 20%;
        margin-right: 0;
        border-right: 4px solid #FF5722;
    }
    
    .speaker-name {
        font-weight: bold;
        margin-bottom: 0.3rem;
        font-size: 0.9rem;
    }
    
    .pro-name {
        color: #2E7D32;
    }
    
    .con-name {
        color: #D84315;
    }
    
    .debate-report {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .status-running {
        color: #FF9800;
        font-weight: bold;
    }
    
    .status-completed {
        color: #4CAF50;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'debate_results' not in st.session_state:
    st.session_state.debate_results = None
if 'debate_running' not in st.session_state:
    st.session_state.debate_running = False
if 'api_key_set' not in st.session_state:
    st.session_state.api_key_set = False

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_api_key():
    """Check if OpenAI API key is configured"""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "sk-your-api-key-here":
        return True
    return False

async def run_debate(topic: str, model: str, max_turns: int, progress_callback=None, pro_persona: str = None, con_persona: str = None):
    """Run the debate and return results"""
    try:
        # Setup OpenAI client
        if progress_callback:
            progress_callback(0, "Setting up OpenAI client...")
        setup_openai_client()
        
        # Convert persona display names to keys
        pro_persona_key = None
        con_persona_key = None
        
        if pro_persona and pro_persona != "None (Default)":
            pro_persona_key, _ = get_persona_by_display_name(pro_persona)
            
        if con_persona and con_persona != "None (Default)":
            con_persona_key, _ = get_persona_by_display_name(con_persona)
        
        # Create agents
        if progress_callback:
            progress_callback(1, "Creating Pro and Con agents...")
        pro_agent = create_pro_agent(model, pro_persona_key)
        con_agent = create_con_agent(model, con_persona_key)
        
        # Create tools
        if progress_callback:
            progress_callback(2, "Setting up agent tools...")
        pro_tool = create_tool_from_agent(
            pro_agent, 
            "Use this to get arguments FOR the motion (pro/affirmative side)"
        )
        con_tool = create_tool_from_agent(
            con_agent, 
            "Use this to get arguments AGAINST the motion (con/negative side)"
        )
        
        # Create orchestrator
        if progress_callback:
            progress_callback(3, "Creating debate orchestrator...")
        orchestrator = create_orchestrator_agent(model, [pro_tool, con_tool])
        
        # Run the debate
        if progress_callback:
            progress_callback(4, "Running debate (this may take a few minutes)...")
        final_report, conversation_log = await verbose_run_final(orchestrator, topic, max_turns, progress_callback, debug_mode=False)
        
        if progress_callback:
            progress_callback(5, "Debate completed! Processing results...")
        
        return {
            'success': True,
            'final_report': final_report,
            'conversation_log': conversation_log,
            'topic': topic,
            'model': model,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'topic': topic,
            'model': model,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def render_conversation_ui(conversation_log):
    """Render the messenger-style conversation interface"""
    if not conversation_log:
        st.warning("No conversation data available. Run a debate first!")
        st.info("💡 **Debug Info**: Check the `logs/` directory for debug files after running a debate.")
        return
    
    for turn in conversation_log:
        speaker = turn.get('speaker', 'Unknown')
        content = turn.get('content', 'No content')
        response = turn.get('response', '')
        
        if speaker == 'ProAgent':
            # Pro agent message (left side, green) - show only response
            if response:  # Only show if there's a response
                st.markdown(f'''
                <div class="pro-message">
                    <div class="speaker-name pro-name">🟢 Pro Agent</div>
                    <div>{response}</div>
                </div>
                ''', unsafe_allow_html=True)
            
        elif speaker == 'ConAgent':
            # Con agent message (right side, red) - show only response
            if response:  # Only show if there's a response
                st.markdown(f'''
                <div class="con-message">
                    <div class="speaker-name con-name">🔴 Con Agent</div>
                    <div>{response}</div>
                </div>
                ''', unsafe_allow_html=True)

def main():
    """Main Streamlit application"""
    
    # Header
    st.title("🎭 AI Debate Club")
    st.markdown("*A sophisticated multi-agent debate system*")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key check
        if check_api_key():
            st.success("✅ OpenAI API Key configured")
            st.session_state.api_key_set = True
        else:
            st.error("❌ OpenAI API Key not found")
            st.markdown("""
            **Setup Instructions:**
            1. Set environment variable: `OPENAI_API_KEY`
            2. Or edit `debate_club.py` directly
            """)
            st.session_state.api_key_set = False
        
        st.divider()
        
        # Debate configuration
        st.subheader("🎯 Debate Settings")
        
        topic = st.text_area(
            "Debate Topic",
            value="Social media platforms should be regulated as public utilities",
            height=100,
            help="Enter the motion/topic for the debate"
        )
        
        model = st.selectbox(
            "AI Model",
            options=["gpt-5-2025-08-07", "gpt-5-mini-2025-08-07", "gpt-4.1-2025-04-14", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini"],
            index=3,  # Default to gpt-4o (4th option)
            help="Choose the OpenAI model for all agents (GPT-5 models recommended for best performance)"
        )
        
        st.divider()
        
        # Persona configuration
        st.subheader("🎭 Agent Personas")
        
        # Get available persona names
        persona_options = ["None (Default)"] + get_persona_names()
        
        pro_persona = st.selectbox(
            "🟢 Choose Pro Agent Persona",
            options=persona_options,
            index=0,  # Default to "None"
            help="Select a personality for the Pro (affirmative) agent"
        )
        
        con_persona = st.selectbox(
            "🔴 Choose Con Agent Persona", 
            options=persona_options,
            index=0,  # Default to "None"
            help="Select a personality for the Con (negative) agent"
        )
        
        # Same persona allowed for both sides for entertaining debates
        max_turns = st.slider(
            "Max Turns",
            min_value=5,
            max_value=50,
            value=20,
            help="Maximum number of turns for the debate"
        )
        
        st.divider()
        
        # Run debate button
        if st.button(
            "🚀 Start Debate", 
            disabled=not st.session_state.api_key_set or st.session_state.debate_running,
            use_container_width=True
        ):
            st.session_state.debate_running = True
            st.rerun()

    # Main content area with tabs
    if st.session_state.debate_running:
        # Show running status
        with st.container():
            st.markdown('<p class="status-running">🔄 Debate in progress...</p>', unsafe_allow_html=True)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Run the debate
            try:
                # Create progress callback
                def update_progress(step, message):
                    if step < 4:
                        # Setup steps: 0-3 map to 0-80%
                        progress = (step + 1) * 20
                        status_text.text(f"Step {step + 1}/7: {message}")
                    else:
                        # Debate steps: 4+ map to 80-100%
                        progress = min(80 + (step - 4) * 10, 100)
                        status_text.text(f"🎭 {message}")
                    progress_bar.progress(int(progress))
                    
                # Run the actual debate with meaningful progress
                results = asyncio.run(run_debate(topic, model, max_turns, update_progress, pro_persona, con_persona))
                
                # Store results and update state
                st.session_state.debate_results = results
                st.session_state.debate_running = False
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if results['success']:
                    st.success("✅ Debate completed successfully!")
                else:
                    st.error(f"❌ Debate failed: {results['error']}")
                
                st.rerun()
                
            except Exception as e:
                st.session_state.debate_running = False
                st.error(f"❌ Error running debate: {str(e)}")
    
    # Display results if available
    if st.session_state.debate_results and not st.session_state.debate_running:
        results = st.session_state.debate_results
        
        if results['success']:
            st.markdown('<p class="status-completed">✅ Debate Completed</p>', unsafe_allow_html=True)
            
            # Create tabs
            tab1, tab2 = st.tabs(["📋 Orchestrator Report", "💬 Conversation UI"])
            
            with tab1:
                st.header("📋 Orchestrator Report")
                st.markdown(f"**Topic:** {results['topic']}")
                st.markdown(f"**Model:** {results['model']}")
                st.markdown(f"**Completed:** {results['timestamp']}")
                
                st.divider()
                
                # Display the final report with error handling
                st.markdown('<div class="debate-report">', unsafe_allow_html=True)
                try:
                    final_report = results.get('final_report', 'No final report available')
                    if final_report and str(final_report).strip():
                        st.markdown(str(final_report))
                    else:
                        st.warning("⚠️ Final report is empty or unavailable")
                        st.info("💡 Check the logs directory for debug information")
                except Exception as e:
                    st.error(f"❌ Error displaying final report: {str(e)}")
                    st.code(f"Raw report data: {repr(results.get('final_report', 'None'))}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Download button
                st.download_button(
                    label="📥 Download Report",
                    data=results['final_report'],
                    file_name=f"debate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
            
            with tab2:
                st.header("💬 Conversation UI")
                st.markdown("*Messenger-style view of the agent interactions*")
                
                # Display conversation
                render_conversation_ui(results['conversation_log'])
                
                # Show conversation statistics
                if results['conversation_log']:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        pro_turns = len([t for t in results['conversation_log'] if t['speaker'] == 'ProAgent'])
                        st.metric("🟢 Pro Agent Turns", pro_turns)
                    with col2:
                        con_turns = len([t for t in results['conversation_log'] if t['speaker'] == 'ConAgent'])
                        st.metric("🔴 Con Agent Turns", con_turns)
                    with col3:
                        total_turns = len(results['conversation_log'])
                        st.metric("📊 Total Exchanges", total_turns)
        
        else:
            st.error(f"❌ Debate failed: {results['error']}")
    
    elif not st.session_state.debate_results and not st.session_state.debate_running:
        # Welcome screen
        st.markdown("""
        ## Welcome to AI Debate Club! 🎭
        
        This is a sophisticated multi-agent debate system where two AI agents engage in formal debates:
        
        ### 🏛️ How it works:
        1. **🟢 Pro Agent** - Argues in favor of the motion
        2. **🔴 Con Agent** - Argues against the motion  
        3. **⚖️ Orchestrator** - Manages the debate flow and produces the final report
        
        ### 📋 Features:
        - **Orchestrator Report**: Professional debate summary with all sections
        - **Conversation UI**: Messenger-style view of agent interactions
        
        ### 🚀 Getting Started:
        1. Configure your OpenAI API key (see sidebar)
        2. Set your debate topic and preferences
        3. Click "Start Debate" to begin!
        """)
        
        # Example topics
        st.subheader("💡 Example Topics:")
        example_topics = [
            "Artificial intelligence should be regulated by government",
            "Remote work is better than office work",
            "Social media has a net positive impact on society",
            "Climate change action should prioritize economic growth",
            "Universal basic income should be implemented globally"
        ]
        
        for i, topic_example in enumerate(example_topics):
            if st.button(f"🎯 {topic_example}", key=f"example_{i}"):
                st.rerun()

if __name__ == "__main__":
    main()