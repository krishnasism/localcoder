from dataclasses import dataclass, field


@dataclass
class AgentContext:
    messages: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    working_directory: str = ""
    current_task: str = ""

    iteration: int = 0
    max_iterations: int = 50


@dataclass
class FinishResult:
    status: str
    summary: str
    artifacts: list[str] = None
