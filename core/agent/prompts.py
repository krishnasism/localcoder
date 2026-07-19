import os
import platform

_system = platform.system()
if _system == "Windows":
    _os_label = "Windows"
    _path_hint = (
        "Prefer backslash paths (e.g. application\\src\\App.tsx). "
        "Forward slashes are also accepted and will be normalized."
    )
elif _system == "Darwin":
    _os_label = "macOS"
    _path_hint = "Use forward-slash paths (e.g. application/src/App.tsx)."
else:
    _os_label = _system or "Linux"
    _path_hint = "Use forward-slash paths (e.g. application/src/App.tsx)."

_OS_BLOCK = f"Operating System: {_os_label} (os.name={os.name}). {_path_hint}"


def build_planning_system_prompt(task: str) -> str:
    return f"""
You are a fast planning agent. Speed matters — finish in 1-2 steps.

## USER TASK (authoritative)
{task}

Rules:
- Do NOT ask clarifying questions. Do NOT say the task is missing.
- A project snapshot is already in the first user message. Use it.
- Read at most 2 files, and only if the snapshot is not enough.
- Prefer planning from the snapshot alone when possible.
- As soon as you can name the files to change, call `plan_finish`.
- `plan_finish.summary` must be a short numbered plan with concrete file paths.
- Do not explore, do not run tests, do not re-list the project.
- {_OS_BLOCK}

Workflow:
1. Glance at the snapshot
2. Optionally read 1-2 key files
3. Immediately call plan_finish
"""


def build_editing_system_prompt(task: str, plan: str) -> str:
    return f"""
You are a fast coding agent executing an approved plan. Prefer action over exploration.

## USER TASK
{task}

## APPROVED PLAN
{plan}

Rules:
- Execute the plan. Do not re-plan. Do not ask clarifying questions.
- Prefer `sed` for small edits, `write_file` for new files.
- If `sed` fails, read that file once, then retry with an exact match.
- Do not restart discovery. Do not call list_files/get_directory_tree.
- Do not repeat the same tool call.
- Use `pytest` for tests, not shell activate/collect loops.
- Call `finish` as soon as the plan is done.
- {_OS_BLOCK}

Workflow: edit → fix failures → verify if needed → finish
"""


PLANNING_SYSTEM_PROMPT = build_planning_system_prompt("<task provided in user message>")
SYSTEM_PROMPT = build_editing_system_prompt(
    "<task provided in user message>", "<plan provided in user message>"
)
