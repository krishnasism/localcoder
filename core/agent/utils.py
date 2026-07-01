import os


def assistant_message_to_dict(message) -> dict:
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
        "write_file",
        "append_to_file",
        "delete_file",
        "move_file",
        "copy_file",
        "move_file_to_directory",
        "mkdir",
    }
)


def is_tool_error(result: str) -> bool:
    lowered = result.lower()
    return (
        lowered.startswith("error")
        or lowered.startswith("tool '")
        or lowered.startswith("unknown tool")
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
        f"- Plan steps:\n{steps_block}\n"
        "Next action: make the next concrete file edit from the plan. "
        "Re-read a file only after you changed it or if an edit failed. "
        "Call finish when every planned change is done."
    )
