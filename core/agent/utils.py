import json
import os
import uuid
from types import SimpleNamespace


def assistant_message_to_dict(message, tool_calls=None) -> dict:
    calls = tool_calls if tool_calls is not None else message.tool_calls
    assistant_message = {
        "role": "assistant",
        "content": message.content or "",
    }
    if calls:
        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in calls
        ]
    return assistant_message


def resolve_target_directory(path: str) -> str:
    candidate = os.path.abspath(path)
    if os.path.isfile(candidate):
        return os.path.dirname(candidate)
    return candidate


def truncate_for_context(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


EDIT_TOOLS = frozenset(
    {
        "sed",
        "insert_after",
        "write_file",
        "append_to_file",
        "delete_file",
        "move_file",
        "copy_file",
        "move_file_to_directory",
        "mkdir",
    }
)

DISCOVERY_TOOLS = frozenset(
    {
        "list_files",
        "get_directory_tree",
        "read_file",
        "find_files",
        "search_text_in_files",
        "run_shell_command",
        "pytest",
        "pytest_with_coverage",
        "change_directory",
        "setup_python_virtual_env",
    }
)

STRUCTURE_TOOLS = frozenset({"list_files", "get_directory_tree"})

MAX_SAME_FILE_READS = 3
MAX_PLANNING_FILE_READS = 2
MAX_IDENTICAL_TOOL_REPEATS = 2
TOOL_RESULT_KEEP_CHARS = 2500
COMPACT_TOOL_RESULT_CHARS = 500
PLANNING_SNAPSHOT_CHARS = 4000


def is_tool_error(result: str) -> bool:
    lowered = result.lower()
    return (
        lowered.startswith("error")
        or lowered.startswith("tool '")
        or lowered.startswith("unknown tool")
        or lowered.startswith("blocked:")
    )


def is_edit_failure(result: str) -> bool:
    return result.startswith("EDIT_FAILED:")


def parse_plan_steps(plan: str) -> list[str]:
    if not plan:
        return []
    steps: list[str] = []
    for line in plan.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0].isdigit() and "." in stripped[:4]:
            steps.append(stripped)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            steps.append(stripped)
    return steps


def looks_like_clarification_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    markers = (
        "could you clarify",
        "can you clarify",
        "please clarify",
        "what would you like",
        "what feature",
        "what task",
        "what should i",
        "need more information",
        "could you provide",
        "unclear what",
        "do you want me to",
        "which feature",
        "no specific task",
        "no concrete",
        "without a concrete",
        "task or feature request was provided",
        "was not provided",
        "wasn't provided",
        "have not been provided",
        "hasn't been provided",
        "if you have a specific",
        "please provide a",
        "cannot produce meaningful",
        "i cannot produce",
        "waiting for",
        "need a specific feature",
        "implicit exploration",
        "only an implicit",
    )
    if any(marker in lowered for marker in markers):
        return True
    return text.count("?") >= 2


def looks_like_missing_task_claim(text: str) -> bool:
    """Model falsely claims the user never gave a task."""
    if not text:
        return False
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "no specific task",
            "no concrete requirement",
            "without a concrete requirement",
            "task or feature request was provided",
            "was not provided",
            "wasn't provided",
            "have not been provided",
            "hasn't been provided",
            "only an implicit exploration",
            "cannot produce meaningful",
            "if you have a specific feature",
            "please clarify and i'll",
            "please clarify and i will",
        )
    )


def task_reminder_message(task: str, phase: str = "planning") -> str:
    if phase == "editing":
        return (
            "REMINDER — the user task is still active and complete:\n"
            f"{task}\n\n"
            "Do not ask for clarification. Continue executing the approved plan "
            "for this task, then call finish when done."
        )
    return (
        "REMINDER — the user task is still active and complete:\n"
        f"{task}\n\n"
        "Do not say the task is missing. Do not ask clarifying questions. "
        "Write a numbered plan of concrete file changes for THIS task and call "
        "plan_finish with that plan in `summary`."
    )


def looks_like_plan(text: str) -> bool:
    steps = parse_plan_steps(text)
    if len(steps) >= 2:
        return True
    if not steps:
        return False
    lowered = text.lower()
    action_verbs = (
        "edit",
        "update",
        "create",
        "add",
        "fix",
        "modify",
        "write",
        "implement",
        "change",
        "remove",
        "delete",
        "run ",
    )
    return any(verb in lowered for verb in action_verbs)


def is_actionable_plan(text: str) -> bool:
    if not text or looks_like_clarification_request(text):
        return False
    if looks_like_plan(text):
        return True
    lowered = text.lower()
    action_verbs = (
        "edit",
        "update",
        "create",
        "add",
        "fix",
        "modify",
        "write",
        "implement",
    )
    has_action = any(verb in lowered for verb in action_verbs)
    has_structure = bool(parse_plan_steps(text))
    return has_action and has_structure


PLANNING_REJECTION_MESSAGE = (
    "plan_finish rejected: `summary` must be a numbered, actionable plan with concrete "
    "file-level steps — not clarifying questions. The user's task is already in the system "
    "prompt and first user message. Read relevant files if needed, then call plan_finish again."
)

PLANNING_CLARIFICATION_NUDGE = (
    "Do not ask clarifying questions and do not claim the task is missing. "
    "The user's task is already in the system prompt and the first user message. "
    "Make reasonable assumptions, write a numbered plan of concrete file changes, and "
    "call plan_finish with that plan in the `summary` parameter."
)

PLANNING_NO_PLAN_NUDGE = (
    "Respond with a numbered plan of concrete file changes for the user task in the "
    "system prompt, then call plan_finish with that plan in the `summary` parameter. "
    "Do not reply with analysis only."
)

REPEATED_TOOL_NUDGE = (
    "You already ran this exact tool call. Do not repeat it. Use the previous result "
    "in context, make a concrete file edit with sed/write_file, or call finish."
)

EMBEDDED_TOOL_NUDGE = "Do not print tool JSON in chat text. Invoke tools through the tool-calling API only."

DISCOVERY_LOOP_NUDGE = (
    "Stop running discovery commands (shell, pytest collect, list_files, repeated reads). "
    "Tests live under `tests/`. Make the next file edit from the approved plan, then "
    "use the `pytest` tool to verify — not run_shell_command."
)

READ_LIMIT_NUDGE = (
    "You have already read this file enough times. Do not read it again. "
    "Either edit it with sed/write_file using the content you already have, "
    "or move to the next plan step / call finish."
)


def tool_call_signature(tool_name: str, args: dict) -> str:
    return f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"


def count_recent_signature_matches(signatures: list[str], signature: str) -> int:
    return sum(1 for item in signatures if item == signature)


def extract_tool_calls_from_content(content: str | None) -> list[dict]:
    """Fallback when the model prints tool JSON in assistant text."""
    if not content:
        return []

    calls: list[dict] = []
    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(content, index)
            if (
                isinstance(obj, dict)
                and isinstance(obj.get("name"), str)
                and isinstance(obj.get("arguments"), dict)
            ):
                calls.append(obj)
        except json.JSONDecodeError:
            continue
    return calls


def materialize_tool_calls(tool_calls, content: str | None) -> list:
    if tool_calls:
        return list(tool_calls)

    embedded = extract_tool_calls_from_content(content)
    if not embedded:
        return []

    materialized = []
    for payload in embedded:
        materialized.append(
            SimpleNamespace(
                id=f"embedded-{uuid.uuid4().hex[:8]}",
                type="function",
                function=SimpleNamespace(
                    name=payload["name"],
                    arguments=json.dumps(payload.get("arguments") or {}),
                ),
            )
        )
    return materialized


def should_skip_assistant_message(
    step: str,
    finish_tool: str,
    resolved_tool_calls: list,
    message,
    extract_summary,
) -> bool:
    """Avoid duplicating plan/final content as a separate assistant_message."""
    for tool_call in resolved_tool_calls:
        if tool_call.function.name != finish_tool:
            continue
        summary = extract_summary(tool_call, message)
        if step == "planning":
            return is_actionable_plan(summary)
        return True

    if (
        step == "planning"
        and message.content
        and not resolved_tool_calls
        and is_actionable_plan(message.content)
    ):
        return True
    return False


def counts_as_editing_progress(tool_name: str, result_text: str) -> bool:
    if tool_name not in EDIT_TOOLS:
        return False
    return not is_tool_error(result_text) and not is_edit_failure(result_text)


def append_nudge(context, kind: str, content: str) -> bool:
    """Append a nudge at most once in a row for the same kind."""
    if context.last_nudge_kind == kind and context.consecutive_nudge_count >= 1:
        context.consecutive_nudge_count += 1
        return False
    context.messages.append({"role": "user", "content": content})
    context.last_nudge_kind = kind
    context.consecutive_nudge_count = 1
    return True


def reset_nudge_tracking(context) -> None:
    context.last_nudge_kind = ""
    context.consecutive_nudge_count = 0


def compact_messages(messages: list, keep_recent_tool_results: int = 6) -> list:
    """Shrink older tool results so long runs stay within context limits."""
    if not messages:
        return messages

    tool_indices = [
        index for index, message in enumerate(messages) if message.get("role") == "tool"
    ]
    if len(tool_indices) <= keep_recent_tool_results:
        compacted = []
        for message in messages:
            if message.get("role") != "tool":
                compacted.append(message)
                continue
            content = str(message.get("content") or "")
            if len(content) > TOOL_RESULT_KEEP_CHARS:
                compacted.append(
                    {
                        **message,
                        "content": truncate_for_context(
                            content, TOOL_RESULT_KEEP_CHARS
                        ),
                    }
                )
            else:
                compacted.append(message)
        return compacted

    protect = set(tool_indices[-keep_recent_tool_results:])
    compacted = []
    for index, message in enumerate(messages):
        if message.get("role") != "tool" or index in protect:
            if message.get("role") == "tool":
                content = str(message.get("content") or "")
                if len(content) > TOOL_RESULT_KEEP_CHARS:
                    compacted.append(
                        {
                            **message,
                            "content": truncate_for_context(
                                content, TOOL_RESULT_KEEP_CHARS
                            ),
                        }
                    )
                else:
                    compacted.append(message)
            else:
                compacted.append(message)
            continue

        content = str(message.get("content") or "")
        compacted.append(
            {
                **message,
                "content": truncate_for_context(content, COMPACT_TOOL_RESULT_CHARS),
            }
        )
    return compacted


def build_execution_reminder(context) -> str:
    modified = ", ".join(sorted(context.files_modified)) or "none yet"
    read_files = ", ".join(sorted(context.files_read)) or "none yet"
    steps = parse_plan_steps(context.plan)
    steps_block = "\n".join(f"  {step}" for step in steps) if steps else context.plan

    return (
        "Execution checkpoint — stay on the approved plan:\n"
        f"- Original task: {context.current_task}\n"
        f"- Files read: {read_files}\n"
        f"- Files modified: {modified}\n"
        f"- Successful edits so far: {context.successful_edits}\n"
        f"- Plan steps:\n{steps_block}\n"
        "Next action: make the next concrete file edit from the plan. "
        "Re-read a file only after you changed it or if an edit failed. "
        "Call finish when every planned change is done."
    )


def build_completion_summary(context) -> str:
    modified = ", ".join(sorted(context.files_modified)) or "none"
    return (
        f"Completed work on: {context.current_task}\n"
        f"Files modified: {modified}\n"
        f"Successful edits: {context.successful_edits}"
    )
