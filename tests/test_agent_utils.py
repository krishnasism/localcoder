from core.agent.models import AgentContext
from core.agent.utils import (
    build_execution_reminder,
    is_edit_failure,
    is_tool_error,
    parse_plan_steps,
)


def test_parse_plan_steps():
    plan = "1. Fix config\n2. Update model\n- Add test"
    steps = parse_plan_steps(plan)
    assert steps == ["1. Fix config", "2. Update model", "- Add test"]


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
