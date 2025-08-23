#!/usr/bin/env python3
"""
AI Debate Club - A Multi-Agent Debate System

This script implements a multi-agent system to simulate formal debates between
two AI agents, orchestrated by a third "Moderator" agent using a state-machine protocol.
"""

# =============================================================================
# 1. IMPORTS & CONFIGURATION
# =============================================================================

import asyncio
import argparse
import os
import sys
from typing import Optional

try:
    from openai_agents import (
        Agent,
        Runner,
        function_tool,
        ItemHelpers,
        ModelSettings,
        ReasoningItem,
        ToolCallItem,
        ToolCallOutputItem,
        MessageOutputItem,
        set_default_openai_client
    )
except ImportError:
    # Fallback to 'agents' if 'openai-agents' is not available
    from agents import (
        Agent,
        Runner,
        function_tool,
        ItemHelpers,
        ModelSettings,
        ReasoningItem,
        ToolCallItem,
        ToolCallOutputItem,
        MessageOutputItem,
        set_default_openai_client
    )

from openai import OpenAI, AsyncOpenAI

# API Key Configuration (for learning environment - use environment variables in production)
OPENAI_API_KEY = "sk-your-api-key-here"  # Replace with your actual API key

# Initialize OpenAI clients
def setup_openai_client():
    """Setup OpenAI clients with API key"""
    api_key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)
    if not api_key or api_key == "sk-your-api-key-here":
        print("⚠️  Warning: Please set your OpenAI API key in the OPENAI_API_KEY environment variable")
        print("   or update the OPENAI_API_KEY variable in this script.")
        sys.exit(1)
    
    custom_openai_client = OpenAI(api_key=api_key)
    custom_async_client = AsyncOpenAI(api_key=api_key)
    set_default_openai_client(custom_async_client)
    return custom_async_client

# Argument Parser Configuration
def setup_argument_parser():
    """Setup command-line argument parser"""
    parser = argparse.ArgumentParser(
        description="AI Debate Club - Multi-Agent Debate System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --topic "Should AI be regulated?"
  %(prog)s --topic "Climate change vs economic growth" --model gpt-4-turbo
        """
    )
    
    parser.add_argument(
        '--topic',
        type=str,
        default="Social media platforms should be regulated as public utilities",
        help='The debate topic/motion (default: "Social media platforms should be regulated as public utilities")'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default="gpt-4o-mini",
        choices=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        help='The OpenAI model to use for all agents (default: gpt-4o-mini)'
    )
    
    parser.add_argument(
        '--max-turns',
        type=int,
        default=20,
        help='Maximum number of turns for the debate (default: 20)'
    )
    
    return parser

# =============================================================================
# 2. L1 SPECIALIST AGENT DEFINITIONS
# =============================================================================

def create_pro_agent(model: str) -> Agent:
    """Create the Pro (Affirmative) debater agent"""
    return Agent(
        name="ProAgent",
        model=model,
        instructions=(
            "You are a skilled debater arguing IN FAVOR of the motion. "
            "Your role is to present compelling arguments that support the given position. "
            "\n\nGuidelines:"
            "\n• Provide clear, logical, and evidence-based arguments"
            "\n• Use specific examples and data when possible"
            "\n• When asked to rebut, directly address your opponent's points"
            "\n• Maintain a professional and respectful tone"
            "\n• Keep responses concise and focused on core arguments"
            "\n• Structure your arguments with clear reasoning"
        ),
        tools=[]
    )

def create_con_agent(model: str) -> Agent:
    """Create the Con (Negative) debater agent"""
    return Agent(
        name="ConAgent",
        model=model,
        instructions=(
            "You are a skilled debater arguing AGAINST the motion. "
            "Your role is to present compelling arguments that oppose the given position. "
            "\n\nGuidelines:"
            "\n• Provide clear, logical, and evidence-based arguments"
            "\n• Use specific examples and data when possible"
            "\n• When asked to rebut, directly address your opponent's points"
            "\n• Maintain a professional and respectful tone"
            "\n• Keep responses concise and focused on core arguments"
            "\n• Structure your arguments with clear reasoning"
        ),
        tools=[]
    )

# =============================================================================
# 3. AGENT-AS-TOOL WRAPPER
# =============================================================================

def create_tool_from_agent(agent: Agent, description: str):
    """
    Wrapper function that converts an Agent into a tool that can be used by the Orchestrator.
    This enables the hierarchical L2->L1 agent architecture.
    """
    async def run_agent_as_tool(query: str) -> str:
        print(f"\n{'='*20} [ SWITCHING CONTEXT ] {'='*20}")
        print(f"Orchestrator delegating to: {agent.name}")
        print(f"Task: {query[:100]}...")
        print(f"{'='*65}\n")
        
        result = await Runner.run(agent, query, max_turns=1)
        output = ItemHelpers.text_message_outputs(result.new_items)
        
        print(f"\n{'='*20} [ RETURNING CONTEXT ] {'='*20}")
        print(f"{agent.name} completed task")
        print(f"Returning control to Orchestrator")
        print(f"{'='*65}\n")
        
        return output if output else f"The {agent.name} did not provide a response."

    return function_tool(
        run_agent_as_tool, 
        name_override=agent.name, 
        description_override=description
    )

# =============================================================================
# 4. L2 ORCHESTRATOR AGENT DEFINITION
# =============================================================================

def create_orchestrator_agent(model: str, tools: list) -> Agent:
    """Create the Debate Moderator (Orchestrator) agent"""
    return Agent(
        name="DebateModerator",
        model=model,
        instructions=(
            "You are an IMPARTIAL debate moderator operating as a strict state machine. "
            "Your SOLE purpose is to manage formal debate flow by calling tools in the correct sequence. "
            "**YOU MUST NOT inject your own opinions or knowledge.**\n\n"
            
            "**DEBATE FLOW STATES:**\n"
            "1. **START** → Call ProAgent: 'The motion is: [MOTION]. Provide your opening statement.'\n"
            "2. **AWAITING_CON_OPENING** → Call ConAgent: 'The motion is: [MOTION]. Provide your opening statement.'\n"
            "3. **AWAITING_CON_REBUTTAL** → Call ConAgent: 'The motion is: [MOTION]. Rebut this opening: [PRO_OPENING]'\n"
            "4. **AWAITING_PRO_REBUTTAL** → Call ProAgent: 'The motion is: [MOTION]. Rebut this opening: [CON_OPENING]'\n"
            "5. **AWAITING_PRO_SUMMARY** → Call ProAgent: 'Motion: [MOTION]. Provide final summary based on: [FULL_HISTORY]'\n"
            "6. **AWAITING_CON_SUMMARY** → Call ConAgent: 'Motion: [MOTION]. Provide final summary based on: [FULL_HISTORY]'\n"
            "7. **REPORTING** → Generate final structured report with all sections\n\n"
            
            "**FINAL REPORT FORMAT:**\n"
            "Structure your final report with these exact sections:\n"
            "## Debate Report: [MOTION]\n\n"
            "### Opening Statement (Pro)\n"
            "[Pro's opening]\n\n"
            "### Opening Statement (Con)\n"
            "[Con's opening]\n\n"
            "### Rebuttal (Con)\n"
            "[Con's rebuttal to Pro]\n\n"
            "### Rebuttal (Pro)\n"
            "[Pro's rebuttal to Con]\n\n"
            "### Final Summary (Pro)\n"
            "[Pro's closing]\n\n"
            "### Final Summary (Con)\n"
            "[Con's closing]\n\n"
            "---\n"
            "*Debate completed by AI Debate Club system*"
        ),
        tools=tools,
        model_settings=ModelSettings(tool_choice="required")
    )

# =============================================================================
# 5. VERBOSE RUNNER FUNCTION
# =============================================================================

async def verbose_run_final(agent: Agent, query: str, max_turns: int = 20) -> tuple:
    """
    MODIFIED: Runs an agent and RETURNS a structured log and the final report.
    Returns: A tuple containing (final_report_string, conversation_log_list)
    """
    conversation_log = []
    
    print(f"\n>>> Starting run for Agent: '{agent.name}' with Query: '{query}' <<<")
    
    result = await Runner.run(agent, query, max_turns=max_turns)
    
    for item in result.new_items:
        # We process the items to build our structured log
        if isinstance(item, ToolCallItem):
            # This is the Orchestrator calling a sub-agent
            tool_name = "Unknown Tool"
            arguments = {}
            
            if hasattr(item, 'raw_item') and item.raw_item:
                raw_call = item.raw_item
                if hasattr(raw_call, 'function') and raw_call.function:
                    tool_name = getattr(raw_call.function, 'name', tool_name)
                    try:
                        import json
                        arguments = json.loads(getattr(raw_call.function, 'arguments', '{}'))
                    except:
                        arguments = {}
            
            # We log this as a "turn" for the sub-agent
            if tool_name in ["ProAgent", "ConAgent"]:
                conversation_log.append({
                    "speaker": tool_name,
                    "content": arguments.get('query', "[No query provided]")
                })

        elif isinstance(item, ToolCallOutputItem):
            # This is the sub-agent's response (Observation)
            speaker = getattr(item, 'tool_name', "[Unknown Tool]")
            output = getattr(item, 'output', "[No output provided]")
            # We find the last turn for this speaker and add their response
            for turn in reversed(conversation_log):
                if turn["speaker"] == speaker and "response" not in turn:
                    turn["response"] = output
                    break
    
    # Get the final report from the Orchestrator
    final_report = ItemHelpers.text_message_outputs(result.new_items)
    
    if not final_report:
        final_report = "The debate concluded without a final report."

    # Return the structured data
    return (final_report, conversation_log)

# =============================================================================
# 6. MAIN EXECUTION BLOCK
# =============================================================================

async def main(topic_override: Optional[str] = None, model_override: Optional[str] = None):
    """
    Main async function that orchestrates the entire debate process.
    Supports both command-line and Jupyter notebook execution.
    """
    
    # Handle command-line arguments (only if not overridden)
    if topic_override is None or model_override is None:
        parser = setup_argument_parser()
        args = parser.parse_args()
        topic = topic_override or args.topic
        model = model_override or args.model
        max_turns = args.max_turns
    else:
        topic = topic_override
        model = model_override
        max_turns = 20
    
    print(f"\n🎭 AI DEBATE CLUB")
    print("="*50)
    print(f"📝 Topic: {topic}")
    print(f"🧠 Model: {model}")
    print(f"🔄 Max Turns: {max_turns}")
    print("="*50)
    
    # Setup OpenAI client
    setup_openai_client()
    
    # Create L1 Specialist Agents
    pro_agent = create_pro_agent(model)
    con_agent = create_con_agent(model)
    print("✅ L1 Debater agents created")
    
    # Create agent-as-tool wrappers
    pro_tool = create_tool_from_agent(
        pro_agent, 
        "Use this to get arguments FOR the motion (pro/affirmative side)"
    )
    con_tool = create_tool_from_agent(
        con_agent, 
        "Use this to get arguments AGAINST the motion (con/negative side)"
    )
    orchestrator_tools = [pro_tool, con_tool]
    print("✅ Agent tools wrapped for orchestrator")
    
    # Create L2 Orchestrator Agent
    orchestrator = create_orchestrator_agent(model, orchestrator_tools)
    print("✅ L2 Orchestrator agent created")
    
    # Run the debate with verbose logging
    print("\n🚀 Starting debate execution...")
    final_report, conversation_log = await verbose_run_final(orchestrator, topic, max_turns)
    
    print(f"\n🎉 Debate completed!")
    print("\n" + "="*80)
    print("FINAL REPORT:")
    print("="*80)
    print(final_report)

# =============================================================================
# EXECUTION ENTRY POINTS
# =============================================================================

if __name__ == "__main__":
    # Command-line execution
    asyncio.run(main())
else:
    # Jupyter notebook execution
    # Uncomment and modify the following lines as needed:
    # custom_topic = "Is remote work better than office work?"
    # custom_model = "gpt-4o"
    # await main(topic_override=custom_topic, model_override=custom_model)
    pass