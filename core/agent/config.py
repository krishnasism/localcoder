import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    model: str = "qwen3.6"
    openai_base_url: str = "http://localhost:11434/v1"
    openai_api_key: str = "local"
    max_iterations: int = 50


def load_agent_config() -> AgentConfig:
    return AgentConfig(
        model=os.getenv("LOCALCODER_MODEL", "qwen3.6"),
        openai_base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "local"),
        max_iterations=int(os.getenv("LOCALCODER_MAX_ITERATIONS", "50")),
    )
