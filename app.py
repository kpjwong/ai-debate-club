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

async def run_debate(topic: str, model: str, max_turns: int):
    """Run the debate and return results"""
    try:
        # Setup OpenAI client
        setup_openai_client()
        
        # Create agents
        pro_agent = create_pro_agent(model)
        con_agent = create_con_agent(model)
        
        # Create tools
        pro_tool = create_tool_from_agent(
            pro_agent, 
            "Use this to get arguments FOR the motion (pro/affirmative side)"
        )
        con_tool = create_tool_from_agent(
            con_agent, 
            "Use this to get arguments AGAINST the motion (con/negative side)"
        )
        
        # Create orchestrator
        orchestrator = create_orchestrator_agent(model, [pro_tool, con_tool])
        
        # Run the debate
        final_report, conversation_log = await verbose_run_final(orchestrator, topic, max_turns)
        
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
            # Pro agent message (left side, green)
            st.markdown(f'''
            <div class="pro-message">
                <div class="speaker-name pro-name">🟢 Pro Agent</div>
                <div><strong>Task:</strong> {content}</div>
                {f"<br><strong>Response:</strong> {response}" if response else ""}
            </div>
            ''', unsafe_allow_html=True)
            
        elif speaker == 'ConAgent':
            # Con agent message (right side, red)
            st.markdown(f'''
            <div class="con-message">
                <div class="speaker-name con-name">🔴 Con Agent</div>
                <div><strong>Task:</strong> {content}</div>
                {f"<br><strong>Response:</strong> {response}" if response else ""}
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
            options=["gpt-4o", "gpt-4-turbo", "gpt-4o-mini"],
            index=0,
            help="Choose the OpenAI model for all agents (gpt-4o recommended for orchestrator)"
        )
        
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
                # Simulate progress updates
                for i in range(5):
                    progress_bar.progress((i + 1) * 20)
                    status_text.text(f"Running debate step {i + 1}/5...")
                    
                # Run the actual debate
                results = asyncio.run(run_debate(topic, model, max_turns))
                
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
                
                # Display the final report
                st.markdown('<div class="debate-report">', unsafe_allow_html=True)
                st.markdown(results['final_report'])
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