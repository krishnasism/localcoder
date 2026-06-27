# Local Coder

Trying out coding with Agents. Did a course on Agents and now trying out. Nothing for production here!

Two phases:
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

- Keep path inputs absolute for best results (well idk)
- If the model starts repeating, try with a more precise prompt

## Example

A prompt that I actually ran:

```sh
python main.py generate_code --query "These tests are failing, please fix FAILED tests/test_agent_config.py::TestLoadAgentConfig::test_load_with_defaults - TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
FAILED tests/test_models.py::TestFinishResultDataclass::test_defaults_for_artifacts - AssertionError: assert None == []" --path "C:\Users\Krish\project\lo
calcoder"

Agent state updated to: initializing
Agent state updated to: planning
Iteration 1 of 50
Agent state updated to: planning
LLM Response: I'll investigate the failing tests and plan the fixes. Let me start by reading the test files and relevant source code.
Running tool: read_file
Running tool: read_file
Iteration 2 of 50
Agent state updated to: planning
Running tool: read_file
Iteration 3 of 50
Agent state updated to: planning
Running tool: read_file
Iteration 4 of 50
Agent state updated to: planning
LLM Response: Now I understand both issues:

**Test 1: `test_load_with_defaults`** - In `core/agent/config.py`, when `os.getenv()` returns `None` (as mocked with `mock_getenv.return_value = None`), the expression `int(os.getenv("LOCALCODER_MAX_ITERATIONS", "50"))` is evaluated as `int(None)` because `return_value = None` applies to all calls. The `default="50"` is only used when the key itself is not found, but `getenv` is being called and returning `None`. However, looking more carefully: when `mock_getenv.return_value = None`, ALL calls to `os.getenv()` return `None`, including for `LOCALCODER_MODEL`, etc. The issue is that `int(None)` throws `TypeError`.

Actually wait - let me re-read. `os.getenv(key, default)` with mock returning None... When you mock `os.getenv` with `return_value = None`, it doesn't use the positional args' defaults. It just returns None for any call. So:
- `os.getenv("LOCALCODER_MODEL", "qwen3.6")` → `None`  
- `os.getenv("LOCALCODER_MAX_ITERATIONS", "50")` → `None`
- Then `int(None)` is called → TypeError in the current code? Actually no, the issue is that `model = None` instead of `"qwen3.6"`, but the actual error says `int() argument must be... not 'NoneType'`.

Wait, looking at it again: with `mock_getenv.return_value = None`, `os.getenv("LOCALCODER_MAX_ITERATIONS", "50")` returns `None`, then `int(None)` fails. That's the error in test 1.

The fix should be in `load_agent_config()` to handle `None` values properly. We need to use a sentinel or conditional logic.

**Test 2: `test_defaults_for_artifacts`** - In `core/agent/models.py`, `artifacts: list[str] = None` sets the default to `None`. The test expects `result.artifacts == []` but it's `None`. The fix is `artifacts: list[str] = field(default_factory=list)`.
Plan finished successfully.
Agent state updated to: planning_completed
Plan of Action:
Now I understand both issues:

**Test 1: `test_load_with_defaults`** - In `core/agent/config.py`, when `os.getenv()` returns `None` (as mocked with `mock_getenv.return_value = None`), the expression `int(os.getenv("LOCALCODER_MAX_ITERATIONS", "50"))` is evaluated as `int(None)` because `return_value = None` applies to all calls. The `default="50"` is only used when the key itself is not found, but `getenv` is being called and returning `None`. However, looking more carefully: when `mock_getenv.return_value = None`, ALL calls to `os.getenv()` return `None`, including for `LOCALCODER_MODEL`, etc. The issue is that `int(None)` throws `TypeError`.

Actually wait - let me re-read. `os.getenv(key, default)` with mock returning None... When you mock `os.getenv` with `return_value = None`, it doesn't use the positional args' defaults. It just returns None for any call. So:
- `os.getenv("LOCALCODER_MODEL", "qwen3.6")` → `None`  
- `os.getenv("LOCALCODER_MAX_ITERATIONS", "50")` → `None`
- Then `int(None)` is called → TypeError in the current code? Actually no, the issue is that `model = None` instead of `"qwen3.6"`, but the actual error says `int() argument must be... not 'NoneType'`.

Wait, looking at it again: with `mock_getenv.return_value = None`, `os.getenv("LOCALCODER_MAX_ITERATIONS", "50")` returns `None`, then `int(None)` fails. That's the error in test 1.

The fix should be in `load_agent_config()` to handle `None` values properly. We need to use a sentinel or conditional logic.

**Test 2: `test_defaults_for_artifacts`** - In `core/agent/models.py`, `artifacts: list[str] = None` sets the default to `None`. The test expects `result.artifacts == []` but it's `None`. The fix is `artifacts: list[str] = field(default_factory=list)`.
Iteration 1 of 50
Agent state updated to: editing
LLM Response: Let me start by reading the relevant source files and test files to understand the exact code that needs to be changed.
Running tool: read_file
Running tool: read_file
Running tool: read_file
Running tool: read_file
Iteration 2 of 50
Agent state updated to: editing
LLM Response: Now I understand both issues clearly:

1. **Test 2 (`test_load_with_defaults`)**: When `mock_getenv.return_value = None`, all calls return `None`, but the test expects defaults to be used. The problem is that `os.getenv(key, default)` with a mock returning `None` for all calls means `int(None)` is called, causing a TypeError. I need to fix `load_agent_config()` to handle `None` properly - by using `or` or checking for `None`.

2. **Test (`test_defaults_for_artifacts`)**: `artifacts: list[str] = None` should be `artifacts: list[str] = field(default_factory=list)` so the default is `[]`, not `None`.

Let me fix both:
Running tool: sed
Iteration 3 of 50
Agent state updated to: editing
LLM Response: Wait - I noticed a typo in my sed command. Let me re-read the file to check what actually happened.
Running tool: read_file
Iteration 4 of 50
Agent state updated to: editing
LLM Response: The sed didn't match because I had a typo in my old_string (`OPENAPI_API_KEY` vs `OPENAI_API_KEY`). Let me rewrite the whole file:
Running tool: write_file
Iteration 5 of 50
Agent state updated to: editing
LLM Response: Now fix the second file - use `field(default_factory=list)` for the `artifacts` default in `FinishResult`:
Running tool: sed
Iteration 6 of 50
Agent state updated to: editing
LLM Response: Now let me verify both files look correct and run the failing tests:
Running tool: read_file
Running tool: read_file
Iteration 7 of 50
Agent state updated to: editing
LLM Response: Both files look correct. Let me now run the previously failing tests:
Running tool: pytest
Running tool: pytest
Iteration 8 of 50
Agent state updated to: editing
LLM Response: Both individual tests pass. Let me verify the entire test suites for both files aren't broken:
Running tool: pytest
Running tool: pytest
Iteration 9 of 50
Agent state updated to: editing
LLM Response: All tests pass across both files. Both fixes are complete.
Task completed successfully.
Agent state updated to: completed
```