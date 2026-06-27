from openai import OpenAI
from dotenv import load_dotenv
from core.agent.config import load_agent_config
from core.agent.models import AgentContext, FinishResult
from core.agent.prompts import PLANNING_SYSTEM_PROMPT, SYSTEM_PROMPT
from core.agent.toolsets import build_tool_registry
from core.agent.utils import (
    assistant_message_to_dict,
    resolve_target_directory,
    truncate_for_context,
)
from core.tools.shell import Shell
from core.state.state import AgentStateManager
from dataclasses import asdict
import json


class CodeAgent:
    def __init__(self):
        load_dotenv()

        self.config = load_agent_config()
        self.model = self.config.model
        self.client = OpenAI(
            base_url=self.config.openai_base_url,
            api_key=self.config.openai_api_key,
        )

        tool_registry = build_tool_registry(
            finish_fn=self.__get_finish_definition(),
            plan_finish_fn=self.__get_plan_finish_definition(),
        )

        self.file_system_tools = tool_registry.file_system_tools
        self.editing_tools = tool_registry.editing_tools
        self.read_only_file_system_tools = tool_registry.read_only_file_system_tools
        self.read_only_planning_tools = tool_registry.read_only_planning_tools
        self.tool_registrations = tool_registry.tool_registrations
        self.tool_registrations["finish"] = self.finish
        self.read_only_tool_registrations = tool_registry.read_only_tool_registrations
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

        target_dir = resolve_target_directory(path)
        change_dir_result = Shell.change_directory(target_dir)
        initial_files = truncate_for_context(Shell.list_files())
        initial_tree = truncate_for_context(Shell.get_directory_tree())

        context = AgentContext(
            current_task=prompt,
            working_directory=Shell.current_directory,
            max_iterations=self.config.max_iterations,
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
            context.messages.append(assistant_message_to_dict(message))

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

        target_dir = resolve_target_directory(path)
        change_dir_result = Shell.change_directory(target_dir)
        initial_files = truncate_for_context(Shell.list_files())
        initial_tree = truncate_for_context(Shell.get_directory_tree())

        context = AgentContext(
            current_task=prompt,
            working_directory=Shell.current_directory,
            max_iterations=self.config.max_iterations,
        )
        context.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n"
                    f"Target file: {path}\n"
                    f"Directory setup: {change_dir_result}\n"
                    f"Current working directory: {Shell.current_directory}\n\n"
                    "Initial project snapshot (already gathered; do not call list_files/get_directory_tree again):\n"
                    f"Files:\n{initial_files}\n\n"
                    f"Tree:\n{initial_tree}"
                ),
            },
        ]

        plan = self.generate_plan_of_action(prompt, path)
        print(f"Plan of Action:\n{plan}")
        context.messages.append(
            {
                "role": "user",
                "content": (
                    "Approved plan to execute:\n"
                    f"{plan}\n"
                    "Now perform the edits and call finish when done."
                ),
            }
        )

        consecutive_structure_only_iterations = 0

        while context.iteration < context.max_iterations:
            context.iteration += 1
            print(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state("editing")
            response = self.__call_llm(context, self.editing_tools)
            message = response.choices[0].message
            context.messages.append(assistant_message_to_dict(message))

            if message.content:
                print(f"LLM Response: {message.content}")

            tool_names = []
            for tool_call in message.tool_calls or []:
                tool_names.append(tool_call.function.name)
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
                            "Stop repeating structure inspection. "
                            "Use the provided plan and perform concrete file edits now. "
                            "Then call finish."
                        ),
                    }
                )

            if consecutive_structure_only_iterations >= 6:
                self.agent_state_manager.update_state("error")
                raise RuntimeError(
                    "Editing is stuck in repeated list_files/get_directory_tree calls. "
                    "Aborting to avoid an infinite loop."
                )

        self.agent_state_manager.update_state("error")
        raise RuntimeError(
            "Editing phase reached max iterations without calling finish. "
            "Model likely did not emit the required completion tool call."
        )

    def explain_code(self, query: str, path: str) -> str:
        with open(path, "r") as file:
            code_content = file.read()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that explains code.",
                },
                {"role": "user", "content": f"Query: {query}\nCode:\n{code_content}"},
            ],
        )
        return response.choices[0].message.content or ""
