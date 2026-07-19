from core.agent.models import AgentContext
from core.agent.utils import (
    append_nudge,
    build_execution_reminder,
    compact_messages,
    extract_tool_calls_from_content,
    is_actionable_plan,
    is_edit_failure,
    is_tool_error,
    looks_like_clarification_request,
    parse_plan_steps,
    should_skip_assistant_message,
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


def test_looks_like_missing_task_claim():
    from core.agent.utils import looks_like_missing_task_claim, task_reminder_message

    text = (
        "However, I notice no specific task or feature request was provided "
        "in the user messages."
    )
    assert looks_like_missing_task_claim(text)
    assert looks_like_clarification_request(text)
    reminder = task_reminder_message("Add dark mode", phase="planning")
    assert "Add dark mode" in reminder
    assert "missing" in reminder.lower()


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


def test_should_skip_assistant_message_for_plan_finish():
    from types import SimpleNamespace
    import json

    def extract_summary(tool_call, message):
        args = json.loads(tool_call.function.arguments)
        return args.get("summary") or message.content or ""

    plan = "1. Edit App.tsx\n2. Add theme toggle"
    tool_call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(
            name="plan_finish",
            arguments=json.dumps({"summary": plan}),
        ),
    )
    message = SimpleNamespace(content=plan, tool_calls=[tool_call])
    assert should_skip_assistant_message(
        "planning", "plan_finish", [tool_call], message, extract_summary
    )


def test_should_not_skip_regular_assistant_message():
    from types import SimpleNamespace

    def extract_summary(_tool_call, message):
        return message.content or ""

    message = SimpleNamespace(content="Reading files now.", tool_calls=[])
    assert not should_skip_assistant_message(
        "planning", "plan_finish", [], message, extract_summary
    )


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


def test_append_nudge_dedupes_same_kind():
    context = AgentContext()
    assert append_nudge(context, "stagnant", "first")
    assert not append_nudge(context, "stagnant", "second")
    assert len([m for m in context.messages if m["role"] == "user"]) == 1
    assert append_nudge(context, "discovery_loop", "third")
    assert len([m for m in context.messages if m["role"] == "user"]) == 2


def test_compact_messages_shortens_old_tool_results():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
    ]
    for index in range(8):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": f"c{index}",
                "content": "x" * 5000,
            }
        )

    compacted = compact_messages(messages, keep_recent_tool_results=3)
    tool_msgs = [m for m in compacted if m["role"] == "tool"]
    assert len(tool_msgs[0]["content"]) < 1000
    assert len(tool_msgs[-1]["content"]) > 4000
