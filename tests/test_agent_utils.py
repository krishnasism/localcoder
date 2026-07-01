from core.agent.models import AgentContext
from core.agent.utils import (
    build_execution_reminder,
    extract_tool_calls_from_content,
    is_actionable_plan,
    is_edit_failure,
    is_tool_error,
    looks_like_clarification_request,
    parse_plan_steps,
    tool_call_signature,
)


def test_parse_plan_steps():
    plan = "1. Fix config\n2. Update model\n- Add test"
    steps = parse_plan_steps(plan)
    assert steps == ["1. Fix config", "2. Update model", "- Add test"]


def test_looks_like_clarification_request():
    text = "Could you clarify what feature you want implemented?"
    assert looks_like_clarification_request(text)
    assert not looks_like_clarification_request("1. Edit api.py\n2. Run tests")


def test_is_actionable_plan_rejects_questions():
    question = "Looking at your project, could you clarify what task you want me to do?"
    assert not is_actionable_plan(question)


def test_is_actionable_plan_accepts_numbered_plan():
    plan = "1. Update App.tsx\n2. Add research page route\n3. Run tests"
    assert is_actionable_plan(plan)


def test_extract_tool_calls_from_content():
    text = """
Let's run this:
{
    "name": "run_shell_command",
    "arguments": {
        "command": "python -m pytest tests"
    }
}
"""
    calls = extract_tool_calls_from_content(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "run_shell_command"


def test_tool_call_signature_stable():
    sig = tool_call_signature("read_file", {"filename": "a.py"})
    assert sig == tool_call_signature("read_file", {"filename": "a.py"})


def test_is_edit_failure():
    assert is_edit_failure("EDIT_FAILED: old_string not found")
    assert not is_edit_failure("SUCCESS: replaced 1 occurrence")


def test_is_tool_error():
    assert is_tool_error("Error reading file")
    assert not is_tool_error("SUCCESS: replaced 1 occurrence")


def test_build_execution_reminder_includes_plan_and_files():
    context = AgentContext(
        current_task="fix tests",
        plan="1. Edit config.py\n2. Run pytest",
        files_read={"config.py"},
        files_modified={"config.py"},
    )
    reminder = build_execution_reminder(context)
    assert "fix tests" in reminder
    assert "config.py" in reminder
    assert "1. Edit config.py" in reminder
