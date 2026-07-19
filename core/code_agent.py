from openai import AsyncOpenAI
from dotenv import load_dotenv
from core.agent.config import load_agent_config
from core.agent.models import AgentContext, FinishResult
from core.agent.prompts import (
    build_editing_system_prompt,
    build_planning_system_prompt,
)
from core.agent.toolsets import build_tool_registry
from core.agent.utils import (
    DISCOVERY_LOOP_NUDGE,
    DISCOVERY_TOOLS,
    EDIT_TOOLS,
    EMBEDDED_TOOL_NUDGE,
    MAX_IDENTICAL_TOOL_REPEATS,
    MAX_SAME_FILE_READS,
    PLANNING_CLARIFICATION_NUDGE,
    PLANNING_NO_PLAN_NUDGE,
    PLANNING_REJECTION_MESSAGE,
    READ_LIMIT_NUDGE,
    REPEATED_TOOL_NUDGE,
    STRUCTURE_TOOLS,
    append_nudge,
    assistant_message_to_dict,
    build_completion_summary,
    build_execution_reminder,
    compact_messages,
    counts_as_editing_progress,
    count_recent_signature_matches,
    is_actionable_plan,
    is_edit_failure,
    is_tool_error,
    looks_like_clarification_request,
    looks_like_missing_task_claim,
    looks_like_plan,
    materialize_tool_calls,
    reset_nudge_tracking,
    resolve_target_directory,
    should_skip_assistant_message,
    task_reminder_message,
    tool_call_signature,
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


class AgentCancelled(Exception):
    """Raised when the client cancels an in-flight agent run."""


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

    async def _ensure_not_cancelled(self, cancel_event: asyncio.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AgentCancelled("Agent run cancelled by client.")

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
            "description": (
                "Complete the planning phase. Pass a numbered, actionable plan in `summary` "
                "(concrete files and changes). Never pass clarifying questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": (
                            "Numbered step-by-step plan with concrete file-level changes. "
                            "Required — do not leave empty."
                        ),
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
        logging.info(f"Model: {self.model}, Tools: {len(tools)}")
        return await self.client.chat.completions.create(
            model=self.model,
            messages=context.messages,
            tools=tools,
            tool_choice="auto",
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
    def _extract_finish_summary(tool_call, message) -> str:
        args = CodeAgent._safe_load_tool_args(tool_call.function.arguments)
        return (args.get("summary") or message.content or "").strip()

    async def _emit_plan(self, on_event: EventCallback | None, plan: str) -> None:
        await self._emit(
            on_event,
            {
                "type": "plan",
                "step": "planning",
                "content": plan,
            },
        )

    @staticmethod
    def _fallback_plan(prompt: str) -> str:
        return (
            f"1. Inspect files relevant to: {prompt}\n"
            f"2. Apply the minimal code changes needed for: {prompt}\n"
            f"3. Verify with read_file or tests\n"
            f"4. Call finish"
        )

    @staticmethod
    def _best_plan_from_messages(messages: list, prompt: str) -> str | None:
        """Prefer a real plan the model already wrote over the generic fallback."""
        for message in reversed(messages):
            if message.get("role") != "assistant":
                continue
            content = (message.get("content") or "").strip()
            if content and is_actionable_plan(content):
                return content
            for tool_call in message.get("tool_calls") or []:
                function = tool_call.get("function") or {}
                if function.get("name") != "plan_finish":
                    continue
                try:
                    args = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    continue
                summary = str(args.get("summary") or "").strip()
                if summary and is_actionable_plan(summary):
                    return summary
        return None

    def _resolve_fallback_plan(self, context: AgentContext) -> str:
        recovered = self._best_plan_from_messages(
            context.messages, context.current_task
        )
        if recovered:
            logger.info("Recovered actionable plan from history instead of generic fallback.")
            return recovered
        return self._fallback_plan(context.current_task)

    def _track_tool_usage(
        self, context: AgentContext, tool_name: str, args: dict, result: str
    ) -> None:
        if tool_name == "read_file" and not is_tool_error(result):
            filename = args.get("filename")
            if filename:
                context.files_read.add(filename)
                context.file_read_counts[filename] = (
                    context.file_read_counts.get(filename, 0) + 1
                )
            return

        if tool_name not in EDIT_TOOLS:
            return

        if is_tool_error(result) or is_edit_failure(result):
            context.edit_failures += 1
            return

        filename = args.get("filename") or args.get("src")
        if filename:
            context.files_modified.add(filename)
            # Allow one re-read after a successful edit of that file.
            context.file_read_counts[filename] = 0
        context.successful_edits += 1

    def _record_tool_signature(
        self, context: AgentContext, tool_name: str, args: dict
    ) -> int:
        signature = tool_call_signature(tool_name, args)
        repeats = count_recent_signature_matches(
            context.recent_tool_signatures, signature
        )
        context.recent_tool_signatures.append(signature)
        context.recent_tool_signatures = context.recent_tool_signatures[-16:]
        return repeats

    def _should_block_tool(
        self, context: AgentContext, tool_name: str, args: dict, repeats: int
    ) -> str | None:
        if repeats >= MAX_IDENTICAL_TOOL_REPEATS:
            return (
                f"Blocked: identical `{tool_name}` call already ran {repeats} times. "
                "Use prior results, edit a file, or call finish/plan_finish."
            )

        if tool_name == "read_file":
            filename = args.get("filename")
            if (
                filename
                and context.file_read_counts.get(filename, 0) >= MAX_SAME_FILE_READS
            ):
                return (
                    f"Blocked: `{filename}` has already been read "
                    f"{context.file_read_counts[filename]} times. {READ_LIMIT_NUDGE}"
                )

        if tool_name in STRUCTURE_TOOLS and any(
            sig.startswith(f"{tool_name}:")
            for sig in context.recent_tool_signatures[:-1]
        ):
            # Soft block only after we already recorded a prior structure call.
            prior = sum(
                1
                for sig in context.recent_tool_signatures[:-1]
                if sig.startswith(f"{tool_name}:")
            )
            if prior >= 1:
                return (
                    f"Blocked: `{tool_name}` already provided. "
                    "Use the existing snapshot and continue."
                )

        return None

    @staticmethod
    def _filter_tool_args(fn, args: dict) -> dict:
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            return args

        if any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        ):
            return args

        allowed = {
            name
            for name, param in signature.parameters.items()
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        filtered = {key: value for key, value in args.items() if key in allowed}
        dropped = sorted(set(args) - set(filtered))
        if dropped:
            logger.warning(
                "Ignored unknown arguments for %s: %s",
                getattr(fn, "__name__", repr(fn)),
                ", ".join(dropped),
            )
        return filtered

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

        args = self._filter_tool_args(fn, args)
        result = fn(**args)
        if inspect.isawaitable(result):
            return await result
        return result

    def _build_initial_user_message(
        self,
        prompt: str,
        path: str,
        change_dir_result: str,
        initial_files: str,
        initial_tree: str,
    ) -> str:
        # Put the task at both ends — local models attend best to edges of long context.
        return (
            "========== USER TASK (COMPLETE — DO NOT ASK FOR CLARIFICATION) ==========\n"
            f"{prompt}\n"
            "========== END USER TASK ==========\n\n"
            f"Target file or folder: {path}\n"
            f"Directory setup: {change_dir_result}\n"
            f"Current working directory: {Shell.current_directory}\n\n"
            "Initial project snapshot (already gathered; do not call "
            "list_files/get_directory_tree again):\n"
            f"Files:\n{initial_files}\n\n"
            f"Tree:\n{initial_tree}\n\n"
            "========== USER TASK REMINDER ==========\n"
            f"{prompt}\n"
            "Plan concrete file-level changes for THIS task, then call plan_finish."
        )

    def _refresh_system_prompt(self, context: AgentContext, step: str) -> None:
        if not context.messages or context.messages[0].get("role") != "system":
            return
        if step == "planning":
            context.messages[0] = {
                "role": "system",
                "content": build_planning_system_prompt(context.current_task),
            }
        elif step == "editing":
            context.messages[0] = {
                "role": "system",
                "content": build_editing_system_prompt(
                    context.current_task, context.plan or "(no plan yet)"
                ),
            }

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
        structure_only_limit: int = 2,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        allowed_tools = self._allowed_tool_names(tools)
        structure_only_tools = structure_only_tools or set(STRUCTURE_TOOLS)
        consecutive_structure_only_iterations = 0
        stagnant_iterations = 0
        iterations_without_edit = 0

        while context.iteration < context.max_iterations:
            await self._ensure_not_cancelled(cancel_event)
            context.iteration += 1
            context.iterations_since_reminder += 1
            logger.info(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state(step)

            if context.iteration % 3 == 0:
                context.messages = compact_messages(context.messages)

            # Keep the authoritative task visible in the system prompt every turn.
            self._refresh_system_prompt(context, step)

            # Re-anchor the task periodically so long tool histories don't bury it.
            if context.iteration > 1 and context.iteration % 4 == 0:
                context.messages.append(
                    {
                        "role": "user",
                        "content": task_reminder_message(
                            context.current_task, phase=step
                        ),
                    }
                )
                reset_nudge_tracking(context)

            await self._emit(
                on_event,
                {
                    "type": "status",
                    "step": step,
                    "message": f"{step.title()} · step {context.iteration}/{context.max_iterations}",
                    "iteration": context.iteration,
                    "max_iterations": context.max_iterations,
                },
            )
            response = await self.__call_llm(context, tools)
            await self._ensure_not_cancelled(cancel_event)
            message = response.choices[0].message
            resolved_tool_calls = materialize_tool_calls(
                message.tool_calls, message.content
            )
            used_embedded_tools = bool(resolved_tool_calls and not message.tool_calls)

            context.messages.append(
                assistant_message_to_dict(
                    message, tool_calls=resolved_tool_calls or None
                )
            )

            if message.content and not should_skip_assistant_message(
                step,
                finish_tool,
                resolved_tool_calls,
                message,
                self._extract_finish_summary,
            ):
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
            iteration_had_repeated_tool = False
            iteration_had_blocked_tool = False

            for tool_call in resolved_tool_calls:
                await self._ensure_not_cancelled(cancel_event)
                tool_names.append(tool_call.function.name)
                if tool_call.function.name == finish_tool:
                    summary = self._extract_finish_summary(tool_call, message)
                    if step == "planning" and not is_actionable_plan(summary):
                        context.messages.append(
                            {
                                "role": "tool",
                                "content": PLANNING_REJECTION_MESSAGE,
                                "tool_call_id": tool_call.id,
                            }
                        )
                        stagnant_iterations += 1
                        if looks_like_clarification_request(
                            summary
                        ) or looks_like_missing_task_claim(summary):
                            append_nudge(
                                context,
                                "planning_clarification",
                                task_reminder_message(
                                    context.current_task, phase="planning"
                                ),
                            )
                        continue

                    logger.info(f"{finish_tool} called successfully.")
                    summary = summary or f"{step.title()} completed."
                    if on_finish is not None:
                        resolved = await on_finish(summary)
                        if resolved is not None:
                            summary = resolved
                    if step == "planning":
                        await self._emit_plan(on_event, summary)
                    await self._emit(
                        on_event,
                        {
                            "type": "status",
                            "step": step,
                            "message": f"{step.title()} completed.",
                        },
                    )
                    return summary

                try:
                    args = self._safe_load_tool_args(tool_call.function.arguments)
                    repeats = self._record_tool_signature(
                        context, tool_call.function.name, args
                    )
                    if repeats >= 1:
                        iteration_had_repeated_tool = True

                    block_reason = self._should_block_tool(
                        context, tool_call.function.name, args, repeats
                    )
                    await self._emit(
                        on_event,
                        {
                            "type": "tool_start",
                            "step": step,
                            "tool": tool_call.function.name,
                            "args": {
                                key: value
                                for key, value in args.items()
                                if key
                                in (
                                    "filename",
                                    "src",
                                    "path",
                                    "command",
                                    "pattern",
                                )
                            },
                        },
                    )

                    if block_reason is not None:
                        iteration_had_blocked_tool = True
                        result_text = block_reason
                    else:
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
                            "result": truncate_for_context(result_text, 6000),
                            "blocked": block_reason is not None,
                        },
                    )
                    context.tool_results[tool_call.id] = result_text
                    if step == "planning" and not is_tool_error(result_text):
                        if tool_call.function.name not in STRUCTURE_TOOLS:
                            iteration_had_progress = True
                    elif counts_as_editing_progress(
                        tool_call.function.name, result_text
                    ):
                        iteration_had_progress = True
                        reset_nudge_tracking(context)

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

            if step == "planning" and message.content and not resolved_tool_calls:
                if looks_like_clarification_request(
                    message.content
                ) or looks_like_missing_task_claim(message.content):
                    append_nudge(
                        context,
                        "planning_clarification",
                        task_reminder_message(context.current_task, phase="planning"),
                    )
                    stagnant_iterations += 2
                elif not is_actionable_plan(message.content):
                    append_nudge(context, "planning_no_plan", PLANNING_NO_PLAN_NUDGE)
                    stagnant_iterations += 1
                elif looks_like_plan(message.content):
                    await self.plan_finish(summary=message.content)
                    await self._emit_plan(on_event, message.content)
                    return message.content

            if (
                step == "editing"
                and message.content
                and (
                    looks_like_clarification_request(message.content)
                    or looks_like_missing_task_claim(message.content)
                )
            ):
                append_nudge(
                    context,
                    "editing_clarification",
                    task_reminder_message(context.current_task, phase="editing"),
                )
                stagnant_iterations += 1

            if iteration_had_progress:
                stagnant_iterations = 0
            else:
                stagnant_iterations += 1

            if iteration_had_edit and not iteration_had_edit_failure:
                iterations_without_edit = 0
                context.discovery_iterations = 0
            elif resolved_tool_calls:
                iterations_without_edit += 1
                if step == "editing" and not iteration_had_edit:
                    if any(name in DISCOVERY_TOOLS for name in tool_names):
                        context.discovery_iterations += 1

            if used_embedded_tools:
                append_nudge(context, "embedded_tools", EMBEDDED_TOOL_NUDGE)

            if iteration_had_repeated_tool or iteration_had_blocked_tool:
                append_nudge(context, "repeated_tool", REPEATED_TOOL_NUDGE)
                stagnant_iterations += 1

            if step == "editing" and context.discovery_iterations >= 3:
                append_nudge(context, "discovery_loop", DISCOVERY_LOOP_NUDGE)
                context.discovery_iterations = 0
                stagnant_iterations += 2

            if (
                step == "editing"
                and iterations_without_edit >= 10
                and not context.files_modified
            ):
                raise RuntimeError(
                    "Editing made no file changes after repeated discovery/tool loops. "
                    "Aborting to avoid an infinite loop."
                )

            if iteration_had_edit_failure:
                append_nudge(
                    context,
                    "edit_failure",
                    (
                        "The last edit failed. Read the target file once, copy the exact "
                        "text you need to change, then retry with `sed` or `write_file`. "
                        "Do not explore unrelated files."
                    ),
                )

            if (
                step == "editing"
                and iterations_without_edit >= 3
                and context.iterations_since_reminder >= 4
            ):
                append_nudge(
                    context, "execution_reminder", build_execution_reminder(context)
                )
                context.iterations_since_reminder = 0
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
                append_nudge(context, "stagnant", nudge)

            if stagnant_iterations >= stagnant_limit * 2:
                if step == "planning":
                    fallback = self._resolve_fallback_plan(context)
                    await self.plan_finish(summary=fallback)
                    await self._emit_plan(on_event, fallback)
                    await self._emit(
                        on_event,
                        {
                            "type": "status",
                            "step": step,
                            "message": "Continuing with best available plan.",
                        },
                    )
                    return fallback

                if context.successful_edits > 0:
                    summary = build_completion_summary(context)
                    await self._emit(
                        on_event,
                        {
                            "type": "status",
                            "step": step,
                            "message": "Wrapping up after progress to avoid a loop.",
                        },
                    )
                    if on_finish is not None:
                        resolved = await on_finish(summary)
                        if resolved is not None:
                            summary = resolved
                    return summary

                append_nudge(
                    context, "execution_reminder", build_execution_reminder(context)
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
                append_nudge(context, "structure", structure_nudge)

            if consecutive_structure_only_iterations >= structure_only_limit * 2:
                if step == "planning":
                    fallback = self._resolve_fallback_plan(context)
                    await self.plan_finish(summary=fallback)
                    await self._emit_plan(on_event, fallback)
                    return fallback
                raise RuntimeError(
                    "Editing is stuck in repeated list_files/get_directory_tree calls. "
                    "Aborting to avoid an infinite loop."
                )

        self.agent_state_manager.update_state("error")

        if step == "editing" and context.successful_edits > 0:
            summary = build_completion_summary(context)
            await self._emit(
                on_event,
                {
                    "type": "status",
                    "step": step,
                    "message": "Max iterations reached; returning completed work.",
                },
            )
            if on_finish is not None:
                resolved = await on_finish(summary)
                if resolved is not None:
                    summary = resolved
            return summary

        if step == "planning":
            fallback = self._resolve_fallback_plan(context)
            await self.plan_finish(summary=fallback)
            await self._emit_plan(on_event, fallback)
            return fallback

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
        cancel_event: asyncio.Event | None = None,
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
                max_iterations=self.config.planning_max_iterations,
            )
            context.messages = [
                {"role": "system", "content": build_planning_system_prompt(prompt)},
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
            stagnant_limit=3,
            cancel_event=cancel_event,
        )

    async def generate_code(
        self,
        prompt: str,
        path: str,
        on_event: EventCallback | None = None,
        cancel_event: asyncio.Event | None = None,
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
        await self._ensure_not_cancelled(cancel_event)

        target_dir = resolve_target_directory(path)
        change_dir_result = await Shell.change_directory(target_dir)
        initial_files = truncate_for_context(await Shell.list_files())
        initial_tree = truncate_for_context(await Shell.get_directory_tree())

        context = AgentContext(
            current_task=prompt,
            working_directory=Shell.current_directory,
            max_iterations=self.config.planning_max_iterations,
        )
        context.messages = [
            {"role": "system", "content": build_planning_system_prompt(prompt)},
            {
                "role": "user",
                "content": self._build_initial_user_message(
                    prompt, path, change_dir_result, initial_files, initial_tree
                ),
            },
        ]

        plan = await self.generate_plan_of_action(
            prompt,
            path,
            on_event=on_event,
            context=context,
            cancel_event=cancel_event,
        )
        context.plan = plan
        logger.debug(f"Plan generated: {context.plan}")

        await self._ensure_not_cancelled(cancel_event)

        context.messages[0] = {
            "role": "system",
            "content": build_editing_system_prompt(prompt, context.plan),
        }
        context.iteration = 0
        context.max_iterations = self.config.max_iterations
        context.discovery_iterations = 0
        context.recent_tool_signatures = []
        reset_nudge_tracking(context)
        context.messages = compact_messages(
            context.messages, keep_recent_tool_results=8
        )
        context.messages.append(
            {
                "role": "user",
                "content": (
                    "Planning is complete. Switch to execution mode.\n\n"
                    "========== USER TASK ==========\n"
                    f"{prompt}\n"
                    "========== APPROVED PLAN ==========\n"
                    f"{context.plan}\n"
                    "========== END ==========\n\n"
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
            stagnant_limit=4,
            cancel_event=cancel_event,
        )

    async def generate_code_stream(
        self,
        prompt: str,
        path: str,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        cancel_event = cancel_event or asyncio.Event()

        async def _on_event(event: dict[str, Any]) -> None:
            await queue.put(event)

        task = asyncio.create_task(
            self.generate_code(
                prompt, path, on_event=_on_event, cancel_event=cancel_event
            )
        )

        while True:
            if cancel_event.is_set() and not task.done():
                task.cancel()

            if task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                if event is not None:
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
        except asyncio.CancelledError:
            yield {
                "type": "status",
                "step": "cancelled",
                "message": "Run cancelled.",
            }
        except AgentCancelled:
            yield {
                "type": "status",
                "step": "cancelled",
                "message": "Run cancelled.",
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
