# Local Coder

## Setup

Setup Python
# Local Coder

Trying out coding with Agents..

It has two phases:
- **Planning**: reads project context and creates a plan.
- **Editing**: executes code changes using filesystem tools.

## Project Structure

- [main.py](main.py) — CLI entrypoint
- [core/code_agent.py](core/code_agent.py) — orchestrates planning/editing loop
- [core/agent/prompts.py](core/agent/prompts.py) — system prompts
- [core/agent/models.py](core/agent/models.py) — dataclasses (`AgentContext`, `FinishResult`)
- [core/agent/config.py](core/agent/config.py) — environment-based runtime config
- [core/agent/toolsets.py](core/agent/toolsets.py) — tool registration builders
- [core/agent/utils.py](core/agent/utils.py) — shared helper utilities
- [core/tools/shell.py](core/tools/shell.py) — filesystem/shell operations
- [core/tools/tools.py](core/tools/tools.py) — tool schemas + tool registry
- [core/state/state.py](core/state/state.py) — agent state manager
- [tests/test_shell.py](tests/test_shell.py), [tests/test_state_manager.py](tests/test_state_manager.py) — pytest tests

## Setup

### 1) Create virtual environment

```sh
pip install uv
uv venv
```

Activate environment:

- Windows (PowerShell):
```sh
.venv\Scripts\Activate.ps1
```

- Windows (cmd):
```sh
.venv\Scripts\activate.bat
```

- macOS/Linux:
```sh
source .venv/bin/activate
```

### 2) Install dependencies

```sh
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
```

### 3) Start local model server (example: Ollama)

```sh
ollama pull qwen3.6
```

By default, the app expects:
- `OPENAI_API_BASE_URL=http://localhost:11434/v1`
- `OPENAI_API_KEY=local`

You can override model/limits via:
- `LOCALCODER_MODEL` (default: `qwen3.6`)
- `LOCALCODER_MAX_ITERATIONS` (default: `50`)

## Usage

### Generate code

```sh
python main.py generate_code --query "Add pytest tests for shell and state modules" --path "C:\Users\Krish\project\localcoder"
```

### Explain code

```sh
python main.py explain_code --query "Explain what this module does" --path "C:\Users\Krish\project\localcoder\core\code_agent.py"
```

## Run tests

```sh
pytest -q
```

## Notes

- Keep path inputs absolute on Windows for best results.
- If the model starts repeating structure inspection, loop guards stop execution with a clear error.
- The planning stage should call `plan_finish`; the editing stage should call `finish`.


