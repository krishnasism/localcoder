from openai import AsyncOpenAI
from dotenv import load_dotenv
from core.agent.config import load_agent_config
from core.agent.models import AgentContext, FinishResult
from core.agent.prompts import PLANNING_SYSTEM_PROMPT, SYSTEM_PROMPT
from core.agent.toolsets import build_tool_registry
from core.agent.utils import (
    EDIT_TOOLS,
    assistant_message_to_dict,
    build_execution_reminder,
    is_edit_failure,
    is_tool_error,
    resolve_target_directory,
    truncate_for_context,
)
from core.tools.shell import Shell
from core.state.state import AgentStateManager
from dataclasses import asdict
import asyncio
import inspect
import json
from typing import Any, AsyncGenerator, Awaitable, Callable
import logging

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]
logger = logging.getLogger(__name__)


class CodeAgent:
    def __init__(self):
        load_dotenv()

        self.config = load_agent_config()
        self.model = self.config.model
        self.client = AsyncOpenAI(
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

    async def _emit(
        self, on_event: EventCallback | None, event: dict[str, Any]
    ) -> None:
        if on_event is not None:
            await on_event(event)

    async def plan_finish(self, summary: str, artifacts: list[str] = None) -> dict:
        """
        Called when the agent has completed the planning phase.
        """

        self.agent_state_manager.update_state("planning_completed")

        result = FinishResult(
            status="planning_completed", summary=summary, artifacts=artifacts or []
        )

        return asdict(result)

    async def finish(self, summary: str, artifacts: list[str] = None) -> dict:
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

    async def __call_llm(self, context: AgentContext, tools: list) -> str:
        logging.info(f"Model: {self.model}, Tools: {tools}")
        return await self.client.chat.completions.create(
            model=self.model,
            messages=context.messages,
            tools=tools,
        )

    @staticmethod
    def _safe_load_tool_args(raw_arguments: str | None) -> dict:
        if not raw_arguments:
            return {}
        try:
            data = json.loads(raw_arguments)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _allowed_tool_names(tools: list) -> set[str]:
        return {tool["function"]["name"] for tool in tools}

    @staticmethod
    def _looks_like_plan(text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        has_steps = "1." in text or "- " in text or "step" in lowered
        has_intent = any(
            keyword in lowered
            for keyword in ["plan", "test", "coverage", "refactor", "create", "update"]
        )
        return has_steps and has_intent

    @staticmethod
    def _fallback_plan(prompt: str) -> str:
        return f"Task focus: {prompt}"

    def _track_tool_usage(
        self, context: AgentContext, tool_name: str, args: dict, result: str
    ) -> None:
        if tool_name == "read_file" and not is_tool_error(result):
            filename = args.get("filename")
            if filename:
                context.files_read.add(filename)
            return

        if tool_name not in EDIT_TOOLS:
            return

        if is_tool_error(result) or is_edit_failure(result):
            context.edit_failures += 1
            return

        filename = args.get("filename") or args.get("src")
        if filename:
            context.files_modified.add(filename)

    async def _execute_tool(
        self,
        tool_call,
        tool_registrations: dict | None = None,
        allowed_tool_names: set[str] | None = None,
    ) -> Any:
        tool_name = tool_call.function.name
        args = self._safe_load_tool_args(tool_call.function.arguments)

        if allowed_tool_names is not None and tool_name not in allowed_tool_names:
            return (
                f"Tool '{tool_name}' is not allowed in this phase. "
                f"Allowed tools: {', '.join(sorted(allowed_tool_names))}"
            )

        fn = (tool_registrations or self.tool_registrations).get(tool_name)

        if fn is None:
            return f"Unknown tool '{tool_name}'"

        result = fn(**args)
        if inspect.isawaitable(result):
            return await result
        return result

    def _build_initial_user_message(self, prompt: str, path: str, change_dir_result: str, initial_files: str, initial_tree: str) -> str:
        return (
            f"{prompt}\n"
            f"Target file or folder: {path}\n"
            f"Directory setup: {change_dir_result}\n"
            f"Current working directory: {Shell.current_directory}\n\n"
            "Initial project snapshot (already gathered; do not call list_files/get_directory_tree again):\n"
            f"Files:\n{initial_files}\n\n"
            f"Tree:\n{initial_tree}"
        )

    async def _run_agent_loop(
        self,
        context: AgentContext,
        tools: list,
        tool_registrations: dict,
        step: str,
        finish_tool: str,
        on_event: EventCallback | None = None,
        on_finish: Callable[[str], Awaitable[str | None]] | None = None,
        structure_only_tools: set[str] | None = None,
        stagnant_limit: int = 4,
        structure_only_limit: int = 3,
    ) -> str:
        allowed_tools = self._allowed_tool_names(tools)
        structure_only_tools = structure_only_tools or {"list_files", "get_directory_tree"}
        consecutive_structure_only_iterations = 0
        stagnant_iterations = 0
        iterations_without_edit = 0

        while context.iteration < context.max_iterations:
            context.iteration += 1
            logger.info(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state(step)
            await self._emit(
                on_event,
                {
                    "type": "status",
                    "step": step,
                    "message": f"{step.title()} iteration {context.iteration}/{context.max_iterations}",
                },
            )
            response = await self.__call_llm(context, tools)
            message = response.choices[0].message

            context.messages.append(assistant_message_to_dict(message))

            if message.content:
                await self._emit(
                    on_event,
                    {
                        "type": "assistant_message",
                        "step": step,
                        "content": message.content,
                    },
                )
                logger.info(f"LLM Response: {message.content}")

            tool_names = []
            iteration_had_progress = False
            iteration_had_edit = False
            iteration_had_edit_failure = False

            for tool_call in message.tool_calls or []:
                tool_names.append(tool_call.function.name)
                if tool_call.function.name == finish_tool:
                    logger.info(f"{finish_tool} called successfully.")
                    summary = message.content or f"{step.title()} completed."
                    if on_finish is not None:
                        resolved = await on_finish(summary)
                        if resolved is not None:
                            summary = resolved
                    await self._emit(
                        on_event,
                        {
                            "type": "status",
                            "step": step,
                            "message": f"{step.title()} completed.",
                            "summary": summary,
                        },
                    )
                    return summary
                try:
                    args = self._safe_load_tool_args(tool_call.function.arguments)
                    await self._emit(
                        on_event,
                        {
                            "type": "tool_start",
                            "step": step,
                            "tool": tool_call.function.name,
                        },
                    )
                    result = await self._execute_tool(
                        tool_call,
                        tool_registrations,
                        allowed_tool_names=allowed_tools,
                    )
                    result_text = str(result)
                    self._track_tool_usage(
                        context, tool_call.function.name, args, result_text
                    )
                    if tool_call.function.name in EDIT_TOOLS:
                        iteration_had_edit = True
                        if is_edit_failure(result_text) or is_tool_error(result_text):
                            iteration_had_edit_failure = True
                    await self._emit(
                        on_event,
                        {
                            "type": "tool_result",
                            "step": step,
                            "tool": tool_call.function.name,
                            "result": result_text,
                        },
                    )
                    context.tool_results[tool_call.id] = result
                    if not is_tool_error(result_text):
                        iteration_had_progress = True

                    context.messages.append(
                        {
                            "role": "tool",
                            "content": result_text,
                            "tool_call_id": tool_call.id,
                        }
                    )
                except Exception as e:
                    error_message = (
                        f"Error executing tool '{tool_call.function.name}': {str(e)}"
                    )
                    await self._emit(
                        on_event,
                        {
                            "type": "error",
                            "step": step,
                            "message": error_message,
                        },
                    )
                    self.agent_state_manager.update_state("error")
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": error_message,
                            "tool_call_id": tool_call.id,
                        }
                    )

            if (
                step == "planning"
                and message.content
                and not (message.tool_calls or [])
                and self._looks_like_plan(message.content)
            ):
                await self.plan_finish(summary=message.content)
                return message.content

            if iteration_had_progress:
                stagnant_iterations = 0
            else:
                stagnant_iterations += 1

            if iteration_had_edit:
                iterations_without_edit = 0
            elif message.tool_calls:
                iterations_without_edit += 1

            if iteration_had_edit_failure:
                context.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The last edit failed. Read the target file once, copy the exact "
                            "text you need to change, then retry with `sed` or `write_file`. "
                            "Do not explore unrelated files."
                        ),
                    }
                )

            if step == "editing" and iterations_without_edit >= 2:
                context.messages.append(
                    {
                        "role": "user",
                        "content": build_execution_reminder(context),
                    }
                )
                iterations_without_edit = 0

            if stagnant_iterations >= stagnant_limit:
                nudge = (
                    "You are looping. Produce a concise plan now and call plan_finish. "
                    "Do not call tools unless strictly necessary."
                    if step == "planning"
                    else (
                        "You are looping without making edits. Execute the next concrete "
                        "file change from the approved plan, then call finish."
                    )
                )
                context.messages.append({"role": "user", "content": nudge})

            if stagnant_iterations >= stagnant_limit * 2:
                if step == "planning":
                    fallback = self._fallback_plan(context.current_task)
                    await self.plan_finish(summary=fallback)
                    await self._emit(
                        on_event,
                        {
                            "type": "status",
                            "step": step,
                            "message": "Using fallback plan.",
                            "summary": fallback,
                        },
                    )
                    return fallback
                context.messages.append(
                    {
                        "role": "user",
                        "content": build_execution_reminder(context),
                    }
                )

            if tool_names and set(tool_names).issubset(structure_only_tools):
                consecutive_structure_only_iterations += 1
            else:
                consecutive_structure_only_iterations = 0

            if consecutive_structure_only_iterations >= structure_only_limit:
                structure_nudge = (
                    "Stop repeating project structure inspection. "
                    "You already have enough structure context. "
                    "Read only files directly relevant to the task and then call plan_finish."
                    if step == "planning"
                    else (
                        "Stop repeating structure inspection. "
                        "Use the approved plan and perform concrete file edits now. "
                        "Then call finish."
                    )
                )
                context.messages.append({"role": "user", "content": structure_nudge})

            if consecutive_structure_only_iterations >= structure_only_limit * 2:
                if step == "planning":
                    context.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You are stuck in repeated list_files/get_directory_tree calls. "
                                "Stop exploring. Produce a concise plan now and call plan_finish."
                            ),
                        }
                    )
                else:
                    raise RuntimeError(
                        "Editing is stuck in repeated list_files/get_directory_tree calls. "
                        "Aborting to avoid an infinite loop."
                    )

        self.agent_state_manager.update_state("error")
        raise RuntimeError(
            f"{step.title()} phase reached max iterations without calling {finish_tool}. "
            "Model likely did not emit the required completion tool call."
        )

    async def generate_plan_of_action(
        self,
        prompt: str,
        path: str,
        on_event: EventCallback | None = None,
        context: AgentContext | None = None,
    ) -> str:
        if context is None:
            self.agent_state_manager.update_state("planning")
            await self._emit(
                on_event,
                {"type": "status", "step": "planning", "message": "Planning started."},
            )

            target_dir = resolve_target_directory(path)
            change_dir_result = await Shell.change_directory(target_dir)
            initial_files = truncate_for_context(await Shell.list_files())
            initial_tree = truncate_for_context(await Shell.get_directory_tree())

            context = AgentContext(
                current_task=prompt,
                working_directory=Shell.current_directory,
                max_iterations=self.config.max_iterations,
            )
            context.messages = [
                {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_initial_user_message(
                        prompt, path, change_dir_result, initial_files, initial_tree
                    ),
                },
            ]

        async def _plan_finish(summary: str) -> str:
            await self.plan_finish(summary=summary)
            return summary

        return await self._run_agent_loop(
            context=context,
            tools=self.read_only_planning_tools,
            tool_registrations=self.read_only_tool_registrations,
            step="planning",
            finish_tool="plan_finish",
            on_event=on_event,
            on_finish=_plan_finish,
        )

    async def generate_code(
        self,
        prompt: str,
        path: str,
        on_event: EventCallback | None = None,
    ) -> str:
        await self._emit(
            on_event,
            {
                "type": "status",
                "step": "initializing",
                "message": "Initializing code generation.",
            },
        )
        self.agent_state_manager.update_state("initializing")

        target_dir = resolve_target_directory(path)
        change_dir_result = await Shell.change_directory(target_dir)
        initial_files = truncate_for_context(await Shell.list_files())
        initial_tree = truncate_for_context(await Shell.get_directory_tree())

        context = AgentContext(
            current_task=prompt,
            working_directory=Shell.current_directory,
            max_iterations=self.config.max_iterations,
        )
        context.messages = [
            {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": self._build_initial_user_message(
                    prompt, path, change_dir_result, initial_files, initial_tree
                ),
            },
        ]

        plan = await self.generate_plan_of_action(
            prompt, path, on_event=on_event, context=context
        )
        context.plan = plan
        await self._emit(
            on_event,
            {
                "type": "plan",
                "step": "planning",
                "content": plan,
            },
        )
        logger.debug(f"Plan generated: {context.plan}")

        context.messages[0] = {"role": "system", "content": SYSTEM_PROMPT}
        context.iteration = 0
        context.messages.append(
            {
                "role": "user",
                "content": (
                    "Planning is complete. Switch to execution mode.\n\n"
                    "Original task:\n"
                    f"{prompt}\n\n"
                    "Approved plan:\n"
                    f"{context.plan}\n\n"
                    "Execute this plan now. Your prior file reads in this conversation "
                    "are still valid — do not restart discovery. "
                    "Make concrete edits one step at a time and call finish when done."
                ),
            }
        )

        async def _on_finish(summary: str) -> str:
            self.agent_state_manager.update_state("completed")
            await self.finish(summary=summary)
            return summary

        return await self._run_agent_loop(
            context=context,
            tools=self.editing_tools,
            tool_registrations=self.tool_registrations,
            step="editing",
            finish_tool="finish",
            on_event=on_event,
            on_finish=_on_finish,
            stagnant_limit=5,
        )

    async def generate_code_stream(
        self, prompt: str, path: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def _on_event(event: dict[str, Any]) -> None:
            await queue.put(event)

        task = asyncio.create_task(self.generate_code(prompt, path, on_event=_on_event))

        while True:
            if task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event
            except TimeoutError:
                continue

        try:
            summary = await task
            yield {
                "type": "final",
                "step": "completed",
                "message": "Code generation completed.",
                "summary": summary,
            }
        except Exception as e:
            yield {
                "type": "error",
                "step": "completed",
                "message": str(e),
            }

    async def explain_code(self, query: str, path: str) -> str:
        def _read_code() -> str:
            with open(path, "r") as file:
                return file.read()

        code_content = await asyncio.to_thread(_read_code)
        response = await self.client.chat.completions.create(
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
