class AgentStateManager:
    def __init__(self):
        self.state = "idle"  # Default state

    @staticmethod
    def get_code_editing_states() -> dict:
        return {
            "initializing": "The agent is initializing the code editing environment.",
            "editing": "The agent is currently editing code.",
            "reviewing": "The agent is reviewing the code changes.",
            "testing": "The agent is testing the code.",
            "committing": "The agent is committing the code changes.",
            "idle": "The agent is idle and not performing any code-related tasks.",
            "completed": "The agent has completed the code editing tasks.",
            "error": "The agent has encountered an error during code editing.",
        }

    def update_state(self, new_state: str) -> None:
        if new_state in self.get_code_editing_states():
            self.state = new_state
            print(f"Agent state updated to: {new_state}")
        else:
            print(f"Invalid state: {new_state}")

    def get_current_state(self) -> str:
        return self.state
