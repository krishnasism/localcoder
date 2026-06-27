from core.agent.models import AgentContext, FinishResult


class TestAgentContextDataclass:
    def test_default_values(self):
        ctx = AgentContext()
        assert ctx.messages == []
        assert ctx.tool_results == {}
        assert ctx.working_directory == ""
        assert ctx.current_task == ""
        assert ctx.iteration == 0
        assert ctx.max_iterations == 50

    def test_custom_initialization(self):
        ctx = AgentContext(
            current_task="Write a hello world file",
            working_directory="/tmp/test",
            max_iterations=20,
        )
        assert ctx.current_task == "Write a hello world file"
        assert ctx.working_directory == "/tmp/test"
        assert ctx.max_iterations == 20
        assert ctx.messages == []
        assert ctx.tool_results == {}
        assert ctx.iteration == 0

    def test_messages_list_is_independent(self):
        ctx1 = AgentContext()
        ctx2 = AgentContext()
        ctx1.messages.append({"role": "user", "content": "hello"})
        assert len(ctx1.messages) == 1
        assert len(ctx2.messages) == 0

    def test_tool_results_dict_is_independent(self):
        ctx1 = AgentContext()
        ctx2 = AgentContext()
        ctx1.tool_results["call1"] = "result"
        assert "call1" in ctx1.tool_results
        assert "call1" not in ctx2.tool_results


class TestFinishResultDataclass:
    def test_defaults_for_artifacts(self):
        result = FinishResult(status="completed", summary="Done")
        assert result.status == "completed"
        assert result.summary == "Done"
        assert result.artifacts == []

    def test_specifying_artifacts(self):
        artifacts = ["file1.py", "file2.py"]
        result = FinishResult(status="completed", summary="Done", artifacts=artifacts)
        assert result.status == "completed"
        assert result.summary == "Done"
        assert result.artifacts == artifacts

    def test_with_none_artifacts(self):
        result = FinishResult(status="planning_completed", summary="Plan done")
        # Default None should remain as the stored value before conversion to dict
        assert result.status == "planning_completed"
