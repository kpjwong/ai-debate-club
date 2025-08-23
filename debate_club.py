import asyncio
import os
from agents import (
    Agent,
    Runner,
    function_tool,
    ItemHelpers,
    ModelSettings,
    # --- 根据您提供的 dir(agents) 输出，我们使用这些确切存在的类 ---
    ReasoningItem,
    ToolCallItem,
    ToolCallOutputItem,
    MessageOutputItem,
    set_default_openai_client
)
from openai import OpenAI, AsyncOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
custom_openai_client = OpenAI(api_key=OPENAI_API_KEY)
custom_async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
set_default_openai_client(custom_async_client)

# --- 正方 Agent ---
ProAgent = Agent(
    name="ProAgent",
    model="gpt-5-mini-2025-08-07",
    instructions=(
        "You are a skilled debater arguing IN FAVOR of the motion. "
        "Provide clear, logical, and evidence-based arguments. "
        "When asked to rebut, directly address the points made by your opponent. "
        "Keep your responses concise and focused on the core argument."
    ),
    tools=[]
)

# --- 反方 Agent ---
ConAgent = Agent(
    name="ConAgent",
    model="gpt-5-mini-2025-08-07",
    instructions=(
        "You are a skilled debater arguing AGAINST the motion. "
        "Provide clear, logical, and evidence-based arguments. "
        "When asked to rebut, directly address the points made by your opponent. "
        "Keep your responses concise and focused on the core argument."
    ),
    tools=[]
)

def create_tool_from_agent(agent: Agent, description: str):
    async def run_agent_as_tool(query: str) -> str:
        print("\n" + "="*20 + f" [ SWITCHING CONTEXT ] " + "="*20)
        print(f"Orchestrator is delegating task to sub-agent: {agent.name}")
        print(f"Sub-agent's task: '{query}'")
        print("="*65 + "\n")
        
        result = await Runner.run(agent, query, max_turns=1)
        output = ItemHelpers.text_message_outputs(result.new_items)
        
        print("\n" + "="*20 + f" [ RETURNING CONTEXT ] " + "="*20)
        print(f"Sub-agent {agent.name} has finished.")
        print(f"Returning result to Orchestrator.")
        print("="*65 + "\n")
        return output if output else "The agent did not provide a response."

    return function_tool(run_agent_as_tool, name_override=agent.name, description_override=description)

pro_agent_tool = create_tool_from_agent(
    agent=ProAgent,
    description="Use this to get the arguments FOR the motion (pro side)."
)
con_agent_tool = create_tool_from_agent(
    agent=ConAgent,
    description="Use this to get the arguments AGAINST the motion (con side)."
)
orchestrator_tools = [pro_agent_tool, con_agent_tool]
print("--- L1 Debater Agents wrapped as Tools for Orchestrator ---")

# --- Orchestrator Agent ---
OrchestratorAgent = Agent(
    name="DebateModerator",
    model="gpt-5-mini-2025-08-07",
    instructions=(
        "You are a STOIC and IMPARTIAL state machine-based debate moderator. "
        "Your SOLE function is to manage the debate flow by calling your tools according to a strict sequence of states. "
        "**YOU MUST NOT USE YOUR OWN KNOWLEDGE OR OPINIONS.**\n"
        "You operate in the following states. After each tool call, you will receive an observation. Based on the complete history, you must determine the current state and execute ONLY the action for the NEXT state.\n"
        "**STATES AND REQUIRED ACTIONS:**\n"
        "1. **START**: This is the initial state. Your action is to call `ProAgent`. The query MUST be: 'The debate motion is: [Insert Full Motion Here]. Please provide your opening statement.'\n"
        "2. **AWAITING_CON_OPENING**: You have the ProAgent's statement. Your action is to call `ConAgent`. The query MUST be: 'The debate motion is: [Insert Full Motion Here]. Please provide your opening statement.'\n"
        "3. **AWAITING_CON_REBUTTAL**: You have both opening statements. Your action is to call `ConAgent`. The query MUST be formatted EXACTLY like this: 'The debate motion is: [Insert Full Motion Here]. Here is the opponent's opening statement. Please provide a point-by-point rebuttal: [Insert ProAgent's full opening statement here]'.\n"
        "4. **AWAITING_PRO_REBUTTAL**: You have the Con's rebuttal. Your action is to call `ProAgent`. The query MUST be formatted EXACTLY like this: 'The debate motion is: [Insert Full Motion Here]. Here is the opponent's opening statement. Please provide a point-by-point rebuttal: [Insert ConAgent's full opening statement here]'.\n"
        "5. **AWAITING_PRO_SUMMARY**: You have both rebuttals. Your action is to call `ProAgent`. The query MUST include the motion AND the entire debate history for full context. For example: 'The debate motion was: [Insert Full Motion Here]. Based on the entire debate history below, provide your final summary: [Insert Full History Here]'.\n"
        "6. **AWAITING_CON_SUMMARY**: You have the Pro's summary. Your action is to call `ConAgent`. The query MUST also include the motion AND the entire debate history for full context.\n"
        "7. **REPORTING**: You have all summaries. This is the final state. Your action is to stop calling tools and output your final answer. Your final answer MUST be a compilation of the entire debate into a single, well-structured report. The report must contain clearly labeled sections for: 'Opening Statement (Pro)', 'Opening Statement (Con)', 'Rebuttal (Con)', 'Rebuttal (Pro)', 'Summary (Pro)', and 'Summary (Con)'. Summarize each round in ONE SENTENCE. "
    ),
    tools=orchestrator_tools,
    # --- 关键修改：强制模型必须使用工具 ---
    # 这会迫使它在第一步就思考“我该用哪个工具？”，而不是“我该如何直接回答？”
    model_settings=ModelSettings(tool_choice="required")
)
print("--- L2 Orchestrator Agent (DebateModerator) Created with ENFORCED instructions ---")

topic = "Anit-wokism is worse than wokism"
max_turns = 20

if asyncio.get_event_loop().is_running():
    # For Jupyter notebooks where event loop is already running
    result = await Runner.run(OrchestratorAgent, topic, max_turns=max_turns)
else:
    # For regular Python runtime
    result = asyncio.run(Runner.run(OrchestratorAgent, topic, max_turns=max_turns))

for item in result.new_items:
    # 我们不再检查 ReasoningItem，因为它不包含可打印的文本。
    # 我们直接关注可观察的行动和结果。

    # 当模型决定调用工具时
    if isinstance(item, ToolCallItem):
        # 思考过程已经隐含在这个行动中了
        print(f"\n🤔 [Thought -> Action] Agent '{OrchestratorAgent.name}' decided to call a tool.")
        
        # --- 关键修复：从 raw_item 中提取信息 ---
        # 根据 OpenAI 的标准 ToolCall 结构，信息应该在 raw_item.function 中
        tool_name_to_print = "[Unknown Tool]"
        arguments_to_print = "[Unknown Arguments]"

        # raw_item 可能有不同的结构，我们安全地访问它
        if hasattr(item, 'raw_item') and item.raw_item:
            raw_tool_call = item.raw_item
            # 检查是否存在 'function' 属性 (标准 OpenAI 格式)
            if hasattr(raw_tool_call, 'function') and raw_tool_call.function:
                function_call = raw_tool_call.function
                if hasattr(function_call, 'name'):
                    tool_name_to_print = function_call.name
                if hasattr(function_call, 'arguments'):
                    arguments_to_print = function_call.arguments
        
        print(f"   | Calling Tool: {tool_name_to_print}")
        
        # 截断过长的参数
        args_str = str(arguments_to_print)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        print(f"   | With Arguments: {args_str}")

    # 当工具执行完毕，结果返回时
    elif isinstance(item, ToolCallOutputItem):
        print(f"\n👀 [Observation] Result from a tool:")
        
        # 安全地获取工具名
        tool_name_to_print = getattr(item, 'tool_name', "[Unknown Source Tool]")
        print(f"   | Source Tool: {tool_name_to_print}")
        
        output_text = getattr(item, 'output', "[No output property found]")
        for line in str(output_text).strip().split('\n'):
            print(f"   | {line}")

final_output = ItemHelpers.text_message_outputs(result.new_items)

if final_output:
    print(f"\n✅ [Final Answer] Agent '{OrchestratorAgent.name}' has concluded:")
    for line in final_output.strip().split('\n'):
        print(f"   | {line}")
else:
    print(f"\n⚠️ [Warning] Agent '{OrchestratorAgent.name}' finished without a clear final text output.")