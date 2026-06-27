from openai import OpenAI
import os
from dotenv import load_dotenv
from core.tools.tools import (
    FS_TOOLS,
    TOOL_REGISTRATIONS,
    READ_ONLY_TOOL_REGISTRATIONS,
    FS_READ_ONLY_TOOLS,
)
from core.tools.shell import Shell
from core.state.state import AgentStateManager
from dataclasses import asdict, dataclass, field
import json

PLANNING_SYSTEM_PROMPT = """
You are an autonomous software engineer.
Your objective is to modify the user's project. However this step is only the planning step. You will only generate a plan first.
Rules:
- Never assume file contents.
- Always inspect the project first before planning. Do not inspect too much. Start to plan as soon as you have enough information.
- Priority is to finish the plan. This provides a clear path to the next agent.
- Plan minimal edits.
- Use available tools whenever needed.
- IMPORTANT: when the plan is ready, you MUST call the `plan_finish` tool with a concise summary.

Recommended workflow:

1. Inspect project
2. Read relevant files
3. Plan code changes if necessary
4. Plan to generate new files if necessary
5. Verify planned modifications
6. Finish
"""

SYSTEM_PROMPT = """
You are an autonomous software engineer.

Your objective is to modify the user's project.

Rules:
- Never assume file contents.
- Always inspect the project before editing.
- Read files before making changes.
- Prefer minimal edits.
- Use available tools whenever needed.
- Verify your changes after editing.
- Continue working until the task is complete.
- Only finish once the requested modification has been made.
- IMPORTANT: when the task is complete, you MUST call the `finish` tool with a concise summary.

Recommended workflow:

1. Inspect project
2. Read relevant files
3. Modify code
4. Generate new files if necessary
5. Verify modifications
6. Finish
"""


@dataclass
class AgentContext:
    messages: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    working_directory: str = ""
    current_task: str = ""

    iteration: int = 0
    max_iterations: int = 50


@dataclass
class FinishResult:
    status: str
    summary: str
    artifacts: list[str] = None


class CodeAgent:
    def __init__(self):
        load_dotenv()
        # self.model = "llama3.2"  #
        self.model = "qwen3.6"
        self.client = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "local"),
        )

        # All Tools
        self.file_system_tools = list(FS_TOOLS)
        self.file_system_tools.append(
            {"type": "function", "function": self.__get_finish_definition()}
        )
        self.tool_registrations = dict(TOOL_REGISTRATIONS)
        self.tool_registrations["finish"] = self.finish

        # Read Only Tools - Planning Phase
        self.read_only_file_system_tools = list(FS_READ_ONLY_TOOLS)
        self.read_only_file_system_tools.append(
            {"type": "function", "function": self.__get_plan_finish_definition()}
        )
        self.read_only_planning_tools = [
            tool
            for tool in self.read_only_file_system_tools
            if tool["function"]["name"] not in {"list_files", "get_directory_tree"}
        ]
        self.read_only_tool_registrations = dict(READ_ONLY_TOOL_REGISTRATIONS)
        self.read_only_tool_registrations["plan_finish"] = self.plan_finish

        self.agent_state_manager = AgentStateManager()

    def plan_finish(self, summary: str, artifacts: list[str] = None) -> dict:
        """
        Called when the agent has completed the planning phase.
        """

        self.agent_state_manager.update_state("planning_completed")

        result = FinishResult(
            status="planning_completed", summary=summary, artifacts=artifacts or []
        )

        return asdict(result)

    def finish(self, summary: str, artifacts: list[str] = None) -> dict:
        """
        Called when the agent has completed the task.
        """

        self.agent_state_manager.update_state("completed")

        result = FinishResult(
            status="completed", summary=summary, artifacts=artifacts or []
        )

        return asdict(result)

    def __get_plan_finish_definition(self):
        return {
            "name": "plan_finish",
            "description": "Indicates that the agent has completed the planning phase and is ready to edit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "A summary of the planning completion.",
                    },
                    "artifacts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of artifacts generated during the planning phase.",
                    },
                },
                "required": ["summary"],
            },
        }

    def __get_finish_definition(self):
        return {
            "name": "finish",
            "description": "Indicates that the agent has completed the task, and no more tasks need to be done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "A summary of the task completion.",
                    },
                    "artifacts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of artifacts generated during the task.",
                    },
                },
                "required": ["summary"],
            },
        }

    def __call_llm(self, context: AgentContext, tools: list) -> str:
        return self.client.chat.completions.create(
            model=self.model,
            messages=context.messages,
            tools=tools,
        )

    @staticmethod
    def _assistant_message_to_dict(message) -> dict:
        assistant_message = {
            "role": "assistant",
            "content": message.content or "",
        }
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in message.tool_calls
            ]
        return assistant_message

    @staticmethod
    def _resolve_target_directory(path: str) -> str:
        candidate = os.path.abspath(path)
        if os.path.isfile(candidate):
            return os.path.dirname(candidate)
        return candidate

    @staticmethod
    def _truncate_for_context(text: str, max_chars: int = 12000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n... (truncated)"

    def _execute_tool(self, tool_call, tool_registrations: dict | None = None):
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments or "{}")

        print(f"Running tool: {tool_name}")

        fn = (tool_registrations or self.tool_registrations).get(tool_name)

        if fn is None:
            raise ValueError(f"Unknown tool '{tool_name}'")

        return fn(**args)

    def generate_plan_of_action(self, prompt: str, path: str) -> str:
        self.agent_state_manager.update_state("planning")

        target_dir = self._resolve_target_directory(path)
        change_dir_result = Shell.change_directory(target_dir)
        initial_files = self._truncate_for_context(Shell.list_files())
        initial_tree = self._truncate_for_context(Shell.get_directory_tree())

        context = AgentContext(
            current_task=prompt,
            working_directory=os.getcwd(),
        )
        context.messages = [
            {
                "role": "system",
                "content": PLANNING_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n"
                    f"Target file or folder: {path}\n"
                    f"Directory setup: {change_dir_result}\n"
                    f"Current working directory: {Shell.current_directory}\n\n"
                    "Initial project snapshot (already gathered; do not call list_files/get_directory_tree again):\n"
                    f"Files:\n{initial_files}\n\n"
                    f"Tree:\n{initial_tree}"
                ),
            },
        ]

        consecutive_structure_only_iterations = 0

        while context.iteration < context.max_iterations:
            context.iteration += 1
            print(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state("planning")
            response = self.__call_llm(context, self.read_only_planning_tools)
            message = response.choices[0].message
            context.messages.append(self._assistant_message_to_dict(message))

            if message.content:
                print(f"LLM Response: {message.content}")

            tool_names = []
            for tool_call in message.tool_calls or []:
                tool_names.append(tool_call.function.name)
                if tool_call.function.name == "plan_finish":
                    print("Plan finished successfully.")
                    self.agent_state_manager.update_state("planning_completed")
                    return message.content or "Planning completed."
                try:
                    result = self._execute_tool(
                        tool_call, self.read_only_tool_registrations
                    )
                    context.tool_results[tool_call.id] = result
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call.id,
                        }
                    )
                except Exception as e:
                    error_message = (
                        f"Error executing tool '{tool_call.function.name}': {str(e)}"
                    )
                    self.agent_state_manager.update_state("error")
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": error_message,
                            "tool_call_id": tool_call.id,
                        }
                    )

            if tool_names and set(tool_names).issubset(
                {"list_files", "get_directory_tree"}
            ):
                consecutive_structure_only_iterations += 1
            else:
                consecutive_structure_only_iterations = 0

            if consecutive_structure_only_iterations >= 3:
                context.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Stop repeating project structure inspection. "
                            "You already have enough structure context. "
                            "Read only files directly relevant to the task and then call plan_finish."
                        ),
                    }
                )

            if consecutive_structure_only_iterations >= 6:
                self.agent_state_manager.update_state("error")
                raise RuntimeError(
                    "Planning is stuck in repeated list_files/get_directory_tree calls. "
                    "Aborting to avoid an infinite loop."
                )

        self.agent_state_manager.update_state("error")
        raise RuntimeError(
            "Planning phase reached max iterations without calling plan_finish. "
            "Model likely did not emit the required completion tool call."
        )

    def generate_code(self, prompt: str, path: str) -> str:
        self.agent_state_manager.update_state("initializing")

        target_dir = self._resolve_target_directory(path)
        Shell.change_directory(target_dir)

        context = AgentContext(
            current_task=prompt,
            working_directory=os.getcwd(),
        )
        context.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {"role": "user", "content": f"{prompt}\nTarget file: {path}"},
        ]

        plan = self.generate_plan_of_action(prompt, path)
        print(f"Plan of Action:\n{plan}")
        context.messages.append(
            {"role": "assistant", "content": f"Plan of Action: {plan}"}
        )
        while context.iteration < context.max_iterations:
            context.iteration += 1
            print(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state("editing")
            response = self.__call_llm(context, self.file_system_tools)
            message = response.choices[0].message
            context.messages.append(self._assistant_message_to_dict(message))

            if message.content:
                print(f"LLM Response: {message.content}")

            for tool_call in message.tool_calls or []:
                if tool_call.function.name == "finish":
                    print("Task completed successfully.")
                    self.agent_state_manager.update_state("completed")
                    return message.content or "Task completed."
                try:
                    result = self._execute_tool(tool_call, self.tool_registrations)
                    context.tool_results[tool_call.id] = result
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call.id,
                        }
                    )
                except Exception as e:
                    error_message = (
                        f"Error executing tool '{tool_call.function.name}': {str(e)}"
                    )
                    self.agent_state_manager.update_state("error")
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": error_message,
                            "tool_call_id": tool_call.id,
                        }
                    )

        self.agent_state_manager.update_state("error")
        raise RuntimeError(
            "Editing phase reached max iterations without calling finish. "
            "Model likely did not emit the required completion tool call."
        )

    def explain_code(self, query: str, path: str) -> str:
        with open(path, "r") as file:
            code_content = file.read()
        return self.__call_llm(
            system="You are a helpful assistant that explains code.",
            user=f"Query: {query}\nCode:\n{code_content}",
            tools=FS_TOOLS,
        )
