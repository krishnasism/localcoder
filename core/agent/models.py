from dataclasses import dataclass, field


@dataclass
class AgentContext:
    messages: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    working_directory: str = ""
    current_task: str = ""

    iteration: int = 0
    max_iterations: int = 50

    plan: str = ""
    files_modified: set[str] = field(default_factory=set)
    files_read: set[str] = field(default_factory=set)
    file_read_counts: dict[str, int] = field(default_factory=dict)
    edit_failures: int = 0
    recent_tool_signatures: list[str] = field(default_factory=list)
    discovery_iterations: int = 0
    consecutive_nudge_count: int = 0
    last_nudge_kind: str = ""
    iterations_since_reminder: int = 0
    successful_edits: int = 0


@dataclass
class FinishResult:
    status: str
    summary: str
    artifacts: list[str] = field(default_factory=list)
