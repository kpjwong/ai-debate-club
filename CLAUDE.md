## Project: AI Debate Club - A Multi-Agent Debate System

### 1. Overview

This project implements a multi-agent system to simulate a formal debate between two AI agents on any given topic. The system is orchestrated by a third "Moderator" agent, which manages the debate flow according to a strict, state-machine-like protocol.

The primary goal is to explore dynamic, multi-turn collaboration between specialized AI agents. Unlike a single language model playing both sides, this architecture enforces cognitive isolation for each debater, leading to more robust and deeply reasoned arguments for their respective stances.

The architecture is hierarchical:
-   **L2 - Orchestrator (`DebateModerator`)**: The master agent responsible for the debate's structure, flow, and turn management. It uses other agents as tools.
-   **L1 - Specialist Agents (`ProAgent`, `ConAgent`)**: The debaters. Each is given a specific, opposing stance and operates within its own isolated context. They do not have tools and rely solely on their instructions and the context provided by the Orchestrator.

This setup is built using the `openai-agents` library and `asyncio`, designed to be run from both standard Python scripts and interactive environments like Jupyter Notebook.

### 2. Core Components

-   **`debate_club.py`**: The main executable script containing all agent definitions and the application logic.
-   **`ProAgent`**: Argues **in favor** of the debate motion.
-   **`ConAgent`**: Argues **against** the debate motion.
-   **`OrchestratorAgent` (`DebateModerator`)**: Manages the debate flow through a state-machine-like prompt. It calls the `ProAgent` and `ConAgent` as tools to generate statements, rebuttals, and summaries.
-   **`verbose_run_final()`**: A custom runner function that executes an agent's task while printing a detailed, step-by-step log of its reasoning, actions, and observations.

### 3. Features

-   **Dynamic Topic Input**: Specify any debate topic via the `--topic` command-line argument.
-   **Selectable LLM Model**: Choose the language model for all agents via the `--model` argument (e.g., `gpt-4o-mini`, `gpt-4-turbo`).
-   **Dual Environment Support**: The script can be run directly as a Python file or executed cell-by-cell in a Jupyter Notebook.
-   **Verbose Logging**: Provides a detailed trace of the multi-agent interaction, including context switching and tool calls, for easy debugging and analysis.
-   **API Key Management**: The OpenAI API key is configured directly in the script for simplicity in this learning environment. (Note: For production, use environment variables.)

### 4. Setup

1.  **Prerequisites**:
    -   Python 3.8+
    -   An active OpenAI API Key.

2.  **Installation**:
    Install the required Python libraries using pip:
    ```bash
    pip install openai openai-agents
    ```

3.  **Configuration**:
    Open the `debate_club.py` script and set your OpenAI API key:
    ```python
    # Find this line in the configuration section
    OPENAI_API_KEY = "sk-..." 
    
    # Replace "sk-..." with your actual key
    OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    ```

### 5. Usage

The script is designed to be flexible for both development and execution.

#### A. Command-Line Interface (Terminal)

This is the recommended way to run a full debate. Use `argparse` to provide the topic and optionally select a model.

**Default Usage (uses default topic and model):**
```bash
python debate_club.py
```

**Specifying a Custom Topic:**
```bash
python debate_club.py --topic "Should social media platforms be regulated as public utilities?"
```

**Specifying a Topic and a Model:**
```bash
python debate_club.py --topic "Is artificial general intelligence a greater threat than climate change?" --model "gpt-4-turbo"
```

**Help:**
To see all available options, run:
```bash
python debate_club.py --help
```

#### B. Jupyter Notebook / IPython Environment

The script is also designed to be run in an interactive environment.

1.  **Copy-Paste**: Copy the entire content of `debate_club.py` into a single Jupyter cell.
2.  **Modify `main()` call**: At the very end of the cell, ensure the final execution line is `await main()`. The script template should already handle this.
3.  **Set Topic and Model**: Before the `main()` call, you can manually define the topic and model if you don't want to use the defaults.
    ```python
    # Example for Jupyter
    # ... (all the script code above) ...
    
    async def main(topic_override=None, model_override=None):
        # ... (the main function will use these overrides) ...
    
    # Manually set topic and run
    custom_topic = "Is remote work the future of the modern workplace?"
    await main(topic_override=custom_topic, model_override="gpt-4o")
    ```
    *Note: The provided script will need a slight modification to the `main` function signature to accept these overrides for cleaner Jupyter usage.*

### 6. Code Structure (`debate_club.py`)

The script is organized into logical sections for clarity:

1.  **Imports & Configuration**: All necessary libraries are imported, and the API key is set here. `argparse` is also configured in this section.
2.  **L1 Specialist Agent Definitions**: `ProAgent` and `ConAgent` are defined with their specific instructions.
3.  **Agent-as-Tool Wrapper**: The `create_tool_from_agent` function is defined here. This is the core logic that allows the Orchestrator to use other agents as tools.
4.  **L2 Orchestrator Agent Definition**: The `OrchestratorAgent` (`DebateModerator`) is defined, including its complex state-machine prompt.
5.  **Verbose Runner Function**: The `verbose_run_final` function provides detailed logging of the agent's internal state.
6.  **Main Execution Block**: The `main` async function ties everything together. The `if __name__ == "__main__":` block handles argument parsing and initiates the `asyncio` event loop for command-line execution.

### 7. Future Maintenance & Updates

-   **Updating Agent Instructions**: To change the behavior or "personality" of the debaters or the moderator, modify the `instructions` string within their respective `Agent(...)` definitions. The state-machine prompt for the `OrchestratorAgent` is particularly sensitive and should be edited with care.
-   **Changing Default Model**: To change the default model, update the `default` value in the `parser.add_argument('--model', ...)` line.
-   **Adding New Agents/Tools**: To extend the system (e.g., adding a `FactCheckerAgent`), define the new L1 agent, create a tool wrapper for it using `create_tool_from_agent`, and add the new tool to the `orchestrator_tools` list. You will also need to update the Orchestrator's instructions to teach it how and when to use this new tool.