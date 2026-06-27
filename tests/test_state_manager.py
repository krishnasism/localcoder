from core.state.state import AgentStateManager


class TestAgentStateManager:
    """Tests for the AgentStateManager class."""

    def test_default_state_is_idle(self):
        manager = AgentStateManager()
        assert manager.get_current_state() == "idle"

    def test_update_to_valid_state(self):
        manager = AgentStateManager()
        manager.update_state("planning")
        assert manager.get_current_state() == "planning"

        manager.update_state("completed")
        assert manager.get_current_state() == "completed"

    def test_update_to_error_state(self):
        manager = AgentStateManager()
        manager.update_state("error")
        assert manager.get_current_state() == "error"

    def test_update_to_invalid_state(self):
        manager = AgentStateManager()
        # Invalid state should not change the current state
        manager.update_state("nonexistent_state")
        assert manager.get_current_state() == "idle"

    def test_get_code_editing_states_returns_all_expected_keys(self):
        states = AgentStateManager.get_code_editing_states()
        expected_states = {
            "initializing",
            "planning",
            "planning_completed",
            "editing",
            "reviewing",
            "testing",
            "committing",
            "idle",
            "completed",
            "error",
        }
        assert set(states.keys()) == expected_states

    def test_all_states_have_descriptions(self):
        states = AgentStateManager.get_code_editing_states()
        for state, description in states.items():
            assert isinstance(description, str)
            assert len(description) > 0


class TestAgentStateManagerMultipleUpdates:
    """Tests covering multiple sequential state updates."""

    def test_sequence_of_updates(self):
        """Simulate a typical workflow: idle -> initializing -> planning -> editing -> completed."""
        manager = AgentStateManager()

        # Start from idle
        assert manager.get_current_state() == "idle"

        manager.update_state("initializing")
        assert manager.get_current_state() == "initializing"

        manager.update_state("planning")
        assert manager.get_current_state() == "planning"

        manager.update_state("editing")
        assert manager.get_current_state() == "editing"

        manager.update_state("completed")
        assert manager.get_current_state() == "completed"

    def test_error_resets_to_idle_on_next_transition(self):
        manager = AgentStateManager()
        manager.update_state("error")
        assert manager.get_current_state() == "error"

        # Transitioning out of error should work
        manager.update_state("idle")
        assert manager.get_current_state() == "idle"
