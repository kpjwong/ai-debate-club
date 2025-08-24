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
        print("Warning: Please set your OpenAI API key in the OPENAI_API_KEY environment variable")
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
        default="gpt-4o",
        choices=["gpt-5-2025-08-07", "gpt-5-mini-2025-08-07", "gpt-4.1-2025-04-14", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini"],
        help='The OpenAI model to use for all agents (default: gpt-4o, GPT-5 models recommended for best performance)'
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
            "\n- Provide clear, logical, and evidence-based arguments"
            "\n- Use specific examples and data when possible"
            "\n- When asked to rebut, directly address your opponent's points"
            "\n- Maintain a professional and respectful tone"
            "\n- Keep responses concise and focused on core arguments"
            "\n- Structure your arguments with clear reasoning"
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
            "\n- Provide clear, logical, and evidence-based arguments"
            "\n- Use specific examples and data when possible"
            "\n- When asked to rebut, directly address your opponent's points"
            "\n- Maintain a professional and respectful tone"
            "\n- Keep responses concise and focused on core arguments"
            "\n- Structure your arguments with clear reasoning"
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
            "You are a debate moderator. Execute the debate sequence by calling tools. DO NOT explain your actions.\n\n"
            
            "DEBATE FLOW (execute each step automatically):\n"
            "1. Call ProAgent with: 'The debate motion is: [motion]. Please provide your opening statement with 3 distinct, numbered points.'\n"
            "2. Call ConAgent with: 'The debate motion is: [motion]. Please provide your opening statement with 3 distinct, numbered points.'\n"
            "3. Call ConAgent with pro's opening for rebuttal\n"
            "4. Call ProAgent with con's opening for rebuttal\n"
            "5. Call ProAgent for final summary with full debate history\n"
            "6. Call ConAgent for final summary with full debate history\n"
            "7. Generate final report using this format:\n\n"
            
            "## Debate Report: [MOTION]\n\n"
            "### Opening Statement (Pro)\n"
            "- **[Key Argument 1]**: Brief explanation\n"
            "- **[Key Argument 2]**: Brief explanation\n"
            "- **[Key Argument 3]**: Brief explanation\n\n"
            "### Opening Statement (Con)\n"
            "- **[Key Counter-Argument 1]**: Brief explanation\n"
            "- **[Key Counter-Argument 2]**: Brief explanation\n"
            "- **[Key Counter-Argument 3]**: Brief explanation\n\n"
            "### Rebuttal (Con)\n"
            "- **On [Pro's Point 1 Topic]**: Brief counter-argument.\n"
            "- **On [Pro's Point 2 Topic]**: Brief counter-argument.\n"
            "- **On [Pro's Point 3 Topic]**: Brief counter-argument.\n\n"
            "### Rebuttal (Pro)\n"
            "- **On [Con's Point 1 Topic]**: Brief counter-argument.\n"
            "- **On [Con's Point 2 Topic]**: Brief counter-argument.\n"
            "- **On [Con's Point 3 Topic]**: Brief counter-argument.\n\n"
            "### Final Position (Pro)\n"
            "- **[Core Conclusion 1]**: Final stance\n"
            "- **[Core Conclusion 2]**: Final stance\n"
            "- **[Core Conclusion 3]**: Final stance\n\n"
            "### Final Position (Con)\n"
            "- **[Core Conclusion 1]**: Final stance\n"
            "- **[Core Conclusion 2]**: Final stance\n"
            "- **[Core Conclusion 3]**: Final stance\n\n"
            "---\n"
            "*Debate completed by AI Debate Club system*"
        ),
        tools=tools,
        model_settings=ModelSettings(tool_choice="required")
    )

# =============================================================================
# 5. VERBOSE RUNNER FUNCTION
# =============================================================================

def clean_unicode_for_windows(text: str) -> str:
    """Clean Unicode characters that cause Windows terminal encoding issues"""
    if not text:
        return text
    
    # Convert to string if not already
    text = str(text)
    
    unicode_replacements = {
        '\u2011': '-',  # Non-breaking hyphen
        '\u2013': '-',  # En dash  
        '\u2014': '--', # Em dash
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
        '\u2022': '-',  # Bullet point
        '\u25cf': '-',  # Black circle
        '\u2460': '1',  # Circled digit one
        '\u2461': '2',  # Circled digit two
        '\u2462': '3',  # Circled digit three
        '\u2010': '-',  # Hyphen
        '\u00ad': '-',  # Soft hyphen
    }
    
    for unicode_char, replacement in unicode_replacements.items():
        text = text.replace(unicode_char, replacement)
    
    return text

def safe_print(*args, **kwargs):
    """Safe print function that cleans Unicode characters before printing"""
    cleaned_args = [clean_unicode_for_windows(str(arg)) for arg in args]
    print(*cleaned_args, **kwargs)

async def verbose_run_final(agent: Agent, query: str, max_turns: int = 20, progress_callback=None, debug_mode: bool = False) -> tuple:
    """
    MODIFIED: Runs an agent and RETURNS a structured log and the final report.
    Returns: A tuple containing (final_report_string, conversation_log_list)
    """
    import json
    from datetime import datetime
    import os
    
    conversation_log = []
    
    print(f"\n>>> Starting run for Agent: '{agent.name}' with Query: '{query}' <<<")
    
    # Initialize progress tracking
    debate_stage_map = {
        "ProAgent": ["Opening statement (Pro)", "Rebuttal (Pro)", "Final summary (Pro)"],
        "ConAgent": ["Opening statement (Con)", "Rebuttal (Con)", "Final summary (Con)"]
    }
    pro_calls = 0
    con_calls = 0
    
    if progress_callback:
        progress_callback(4, "Pro Agent: Preparing opening statement...")
    
    result = await Runner.run(agent, query, max_turns=max_turns)
    
    for item in result.new_items:
        # We process the items to build our structured log
        if isinstance(item, ToolCallItem):
            # This is the Orchestrator calling a sub-agent
            tool_name = "Unknown Tool"
            arguments = {}
            
            # FIXED: Use actual attributes from the debug log
            if hasattr(item, 'raw_item') and item.raw_item:
                raw_call = item.raw_item
                # From debug log: raw_item has 'name' and 'arguments' directly
                tool_name = getattr(raw_call, 'name', tool_name)
                try:
                    args_str = getattr(raw_call, 'arguments', '{}')
                    arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
                except:
                    arguments = {}
            
            # Fallback methods if the above doesn't work
            if tool_name == "Unknown Tool":
                if hasattr(item, 'name') and item.name:
                    tool_name = item.name
                elif hasattr(item, 'tool_name') and item.tool_name:
                    tool_name = item.tool_name
            
            # ULTRA-COMPREHENSIVE Debug: Try every possible way to extract data (disabled by default to avoid Unicode issues)
            if debug_mode:
                safe_print(f"\nULTRA-DEBUGGING ToolCallItem:")
                safe_print(f"    Basic Info:")
                safe_print(f"      - Type: {type(item).__name__}")
                safe_print(f"      - All attributes: {list(item.__dict__.keys())}")
                safe_print(f"      - All methods: {[m for m in dir(item) if not m.startswith('_') and callable(getattr(item, m, None))]}")
            
            print(f"    Direct Attributes:")
            for attr_name in item.__dict__.keys():
                attr_value = getattr(item, attr_name, None)
                if attr_name not in ['raw_item']:
                    print(f"      - {attr_name}: {repr(attr_value)}")
                else:
                    print(f"      - {attr_name}: {type(attr_value).__name__}")
                    # Deep inspect raw_item
                    if attr_value:
                        print(f"         * raw_item attributes: {list(attr_value.__dict__.keys()) if hasattr(attr_value, '__dict__') else 'No __dict__'}")
                        if hasattr(attr_value, 'function'):
                            func = attr_value.function
                            print(f"         * function type: {type(func).__name__}")
                            print(f"         * function attributes: {list(func.__dict__.keys()) if hasattr(func, '__dict__') else 'No __dict__'}")
                            if hasattr(func, 'name'):
                                print(f"         * function.name: {repr(func.name)}")
                            if hasattr(func, 'arguments'):
                                print(f"         * function.arguments: {repr(func.arguments)}")
            
            print(f"    Multiple Extraction Attempts:")
            # Try method 1: Direct attributes
            method1_name = getattr(item, 'name', None)
            method1_args = getattr(item, 'arguments', None)
            print(f"      - Method 1 (direct): name={repr(method1_name)}, args={repr(method1_args)}")
            
            # Try method 2: Through tool_name
            method2_name = getattr(item, 'tool_name', None)  
            print(f"      - Method 2 (tool_name): {repr(method2_name)}")
            
            # Try method 3: Through raw_item
            method3_name, method3_args = None, None
            if hasattr(item, 'raw_item') and item.raw_item:
                raw = item.raw_item
                if hasattr(raw, 'function'):
                    method3_name = getattr(raw.function, 'name', None)
                    method3_args = getattr(raw.function, 'arguments', None)
            print(f"      - Method 3 (raw_item): name={repr(method3_name)}, args={repr(method3_args)}")
            
            # Try method 4: vars() inspection
            try:
                vars_data = vars(item)
                print(f"      - Method 4 (vars): {vars_data}")
            except:
                print(f"      - Method 4 (vars): Failed")
            
            print(f"    Final Extraction Results:")
            print(f"      - tool_name: '{tool_name}'")
            print(f"      - arguments: {arguments}")
            
            # We log this as a "turn" for the sub-agent
            if tool_name in ["ProAgent", "ConAgent"]:
                content = arguments.get('query', arguments.get('input', "[No query provided]"))
                # Clean Unicode from content before logging
                content = clean_unicode_for_windows(content)
                conversation_log.append({
                    "speaker": tool_name,
                    "content": content
                })
                if debug_mode:
                    safe_print(f" Added conversation turn: {tool_name} -> {content[:50]}...")
                
                # Real-time progress updates during actual debate
                if progress_callback:
                    if tool_name == "ProAgent":
                        stage_messages = [
                            "Pro Agent: Creating opening statement...",
                            "Pro Agent: Preparing rebuttal...", 
                            "Pro Agent: Writing final summary..."
                        ]
                        if pro_calls < len(stage_messages):
                            progress_callback(4 + pro_calls * 0.5, stage_messages[pro_calls])
                        pro_calls += 1
                    elif tool_name == "ConAgent":
                        stage_messages = [
                            "Con Agent: Creating opening statement...",
                            "Con Agent: Preparing rebuttal...",
                            "Con Agent: Writing final summary..."
                        ]
                        if con_calls < len(stage_messages):
                            progress_callback(4.25 + con_calls * 0.5, stage_messages[con_calls])
                        con_calls += 1

        elif isinstance(item, ToolCallOutputItem):
            # This is the sub-agent's response (Observation)
            # FIXED: From debug log, we know these items have 'output' directly
            output = getattr(item, 'output', "[No output provided]")
            
            # For speaker, we need to match it with the corresponding ToolCallItem
            # For now, let's extract from raw_item if available
            speaker = "[Unknown Tool]"
            if hasattr(item, 'raw_item') and item.raw_item:
                raw_output = item.raw_item
                if isinstance(raw_output, dict) and 'call_id' in raw_output:
                    # Try to find matching call_id in previous ToolCallItems
                    call_id = raw_output['call_id']
                    # For now, we'll use a simpler approach and match by position
                    pass
            
            # Fallback: try to get speaker from recent conversation log entries
            if conversation_log and not speaker or speaker == "[Unknown Tool]":
                # Find the most recent entry without a response
                for turn in reversed(conversation_log):
                    if "response" not in turn:
                        speaker = turn["speaker"]
                        break
            
            # ULTRA-COMPREHENSIVE Debug for ToolCallOutputItem
            if debug_mode:
                safe_print(f"\nULTRA-DEBUGGING ToolCallOutputItem:")
                safe_print(f"    Basic Info:")
                safe_print(f"      - Type: {type(item).__name__}")
                safe_print(f"      - All attributes: {list(item.__dict__.keys())}")
                safe_print(f"      - All methods: {[m for m in dir(item) if not m.startswith('_') and callable(getattr(item, m, None))]}")
            
            print(f"    Direct Attributes:")
            for attr_name in item.__dict__.keys():
                attr_value = getattr(item, attr_name, None)
                if len(str(attr_value)) < 200:  # Show short values
                    print(f"      - {attr_name}: {repr(attr_value)}")
                else:
                    print(f"      - {attr_name}: <{type(attr_value).__name__} length={len(str(attr_value))}>")
                    # Show first 100 characters of long values
                    print(f"         Preview: {repr(str(attr_value)[:100])}...")
            
            print(f"    Multiple Extraction Attempts:")
            # Try method 1: tool_name attribute
            method1_speaker = getattr(item, 'tool_name', None)
            method1_output = getattr(item, 'output', None)
            print(f"      - Method 1 (tool_name/output): speaker={repr(method1_speaker)}, output_len={len(str(method1_output)) if method1_output else 0}")
            
            # Try method 2: name attribute 
            method2_speaker = getattr(item, 'name', None)
            method2_output = getattr(item, 'result', None)
            print(f"      - Method 2 (name/result): speaker={repr(method2_speaker)}, output_len={len(str(method2_output)) if method2_output else 0}")
            
            # Try method 3: Direct inspection
            method3_speaker = getattr(item, 'function_name', None)
            method3_output = getattr(item, 'content', None)
            print(f"      - Method 3 (function_name/content): speaker={repr(method3_speaker)}, output_len={len(str(method3_output)) if method3_output else 0}")
            
            # Try method 4: vars() inspection
            try:
                vars_data = vars(item)
                print(f"      - Method 4 (vars): {list(vars_data.keys())}")
                for k, v in vars_data.items():
                    if len(str(v)) < 100:
                        print(f"         * {k}: {repr(v)}")
                    else:
                        print(f"         * {k}: <{type(v).__name__} length={len(str(v))}>")
            except:
                print(f"      - Method 4 (vars): Failed")
            
            print(f"    Final Extraction Results:")
            print(f"      - speaker: '{speaker}'")
            print(f"      - output length: {len(str(output))}")
            
            # We find the last turn for this speaker and add their response
            for turn in reversed(conversation_log):
                if turn["speaker"] == speaker and "response" not in turn:
                    # Clean Unicode from output before storing
                    cleaned_output = clean_unicode_for_windows(str(output))
                    turn["response"] = cleaned_output
                    if debug_mode:
                        safe_print(f" Added response to {speaker}: {str(cleaned_output)[:50]}...")
                    break
        
        elif isinstance(item, MessageOutputItem):
            # This is the Orchestrator's final message or intermediate reasoning
            print(f"\n  MessageOutputItem found:")
            if hasattr(item, 'raw_item') and item.raw_item:
                raw_msg = item.raw_item
                if hasattr(raw_msg, 'content'):
                    content_items = raw_msg.content if isinstance(raw_msg.content, list) else [raw_msg.content]
                    for content in content_items:
                        if hasattr(content, 'text'):
                            cleaned_text = clean_unicode_for_windows(content.text[:100])
                            print(f"   Message: {cleaned_text}...")
                            # If this contains "REPORTING" or looks like a final report, it's our final answer
                            if "REPORTING" in content.text or "Debate Report:" in content.text:
                                print("     This appears to be the final debate report!")
    
    # Get the final report from the Orchestrator with comprehensive error handling
    try:
        print(f"\n EXTRACTING FINAL REPORT:")
        print(f"   - Total result items: {len(result.new_items)}")
        
        final_report = ItemHelpers.text_message_outputs(result.new_items)
        print(f"   - Raw final_report type: {type(final_report)}")
        print(f"   - Raw final_report length: {len(str(final_report)) if final_report else 0}")
        
        if final_report:
            # Clean the final report to avoid display issues
            final_report = str(final_report).strip()
            # Remove any potential problematic characters and Unicode
            final_report = final_report.replace('\x00', '').replace('\r\n', '\n')
            final_report = clean_unicode_for_windows(final_report)
            print(f"   - Cleaned final_report length: {len(final_report)}")
            print(f"   - Final report preview: {repr(final_report[:200])}...")
        else:
            print(f"   - Final report is empty/None")
            final_report = "The debate concluded without a final report."
            
    except Exception as e:
        print(f"     Error extracting final report: {e}")
        print(f"    Available result.new_items types: {[type(item).__name__ for item in result.new_items]}")
        final_report = f"Error generating final report: {str(e)}"

    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Save debug logs with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save conversation log
    conversation_log_file = os.path.join(logs_dir, f"conversation_{timestamp}.json")
    with open(conversation_log_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'query': query,
            'agent': agent.name,
            'conversation_log': conversation_log,
            'conversation_log_length': len(conversation_log)
        }, f, indent=2, ensure_ascii=False)
    
    # Save final report
    report_file = os.path.join(logs_dir, f"report_{timestamp}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Debate Report - {timestamp}\n")
        f.write(f"**Query:** {query}\n\n")
        f.write(final_report)
    
    # Save raw result items for debugging
    raw_debug_file = os.path.join(logs_dir, f"raw_debug_{timestamp}.json")
    debug_data = []
    for i, item in enumerate(result.new_items):
        item_debug = {
            'index': i,
            'type': type(item).__name__,
            'attributes': {},
            'methods': [method for method in dir(item) if not method.startswith('_')]
        }
        
        # Capture all attributes safely
        for k, v in item.__dict__.items():
            if not k.startswith('_'):
                try:
                    item_debug['attributes'][k] = str(v)
                except:
                    item_debug['attributes'][k] = f"<{type(v).__name__}>"
        
        # Special handling for ToolCallItem and ToolCallOutputItem
        if isinstance(item, ToolCallItem):
            item_debug['special_checks'] = {
                'has_name': hasattr(item, 'name'),
                'has_tool_name': hasattr(item, 'tool_name'),
                'has_arguments': hasattr(item, 'arguments'),
                'has_raw_item': hasattr(item, 'raw_item')
            }
            if hasattr(item, 'raw_item') and item.raw_item:
                try:
                    item_debug['raw_item_details'] = {
                        'type': type(item.raw_item).__name__,
                        'has_function': hasattr(item.raw_item, 'function'),
                        'attributes': {k: str(v) for k, v in item.raw_item.__dict__.items() if not k.startswith('_')}
                    }
                except:
                    item_debug['raw_item_details'] = "Error accessing raw_item"
        
        debug_data.append(item_debug)
    
    with open(raw_debug_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'total_items': len(result.new_items),
            'items': debug_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Debug logs saved:")
    print(f"   - Conversation: {conversation_log_file}")
    print(f"   - Report: {report_file}")
    print(f"   - Raw Debug: {raw_debug_file}")
    print(f"   - Conversation log entries: {len(conversation_log)}")

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
    
    print(f"\nAI DEBATE CLUB")
    print("="*50)
    print(f"Topic: {topic}")
    print(f"Model: {model}")
    print(f"Max Turns: {max_turns}")
    print("="*50)
    
    # Setup OpenAI client
    setup_openai_client()
    
    # Create L1 Specialist Agents
    pro_agent = create_pro_agent(model)
    con_agent = create_con_agent(model)
    print(" L1 Debater agents created")
    
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
    print(" Agent tools wrapped for orchestrator")
    
    # Create L2 Orchestrator Agent
    orchestrator = create_orchestrator_agent(model, orchestrator_tools)
    print(" L2 Orchestrator agent created")
    
    # Run the debate with verbose logging
    print("\nStarting debate execution...")
    final_report, conversation_log = await verbose_run_final(orchestrator, topic, max_turns, None, debug_mode=False)
    
    print(f"\nDebate completed!")
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