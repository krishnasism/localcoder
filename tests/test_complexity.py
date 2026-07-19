from core.agent.complexity import classify_prompt, synthetic_plan_for_prompt


def test_classify_trivial_named_file_edit():
    prompt = "In App.tsx, change the button label from Save to Submit"
    assert classify_prompt(prompt) == "trivial"


def test_classify_trivial_typo_fix():
    prompt = "Fix typo in application/src/App.css: 'colr' should be 'color'"
    assert classify_prompt(prompt) == "trivial"


def test_classify_medium_short_with_file():
    prompt = "Update api.py to return 400 when path is empty"
    assert classify_prompt(prompt) in {"trivial", "medium"}


def test_classify_hard_refactor():
    prompt = "Refactor the entire agent architecture to support multi-agent workflows"
    assert classify_prompt(prompt) == "hard"


def test_classify_hard_implement_feature():
    prompt = (
        "Implement a new feature for project-wide semantic search across the codebase"
    )
    assert classify_prompt(prompt) == "hard"


def test_synthetic_plan_includes_file():
    plan = synthetic_plan_for_prompt("Rename title in App.tsx to Localcoder")
    assert "App.tsx" in plan
    assert "1." in plan
