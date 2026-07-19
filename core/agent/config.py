import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    model: str = "qwen3.6"
    openai_base_url: str = "http://localhost:11434/v1"
    openai_api_key: str = "local"
    max_iterations: int = 40
    planning_max_iterations: int = 12


def load_agent_config() -> AgentConfig:
    def _getenv(key: str, default: str) -> str:
        val = os.getenv(key, default)
        return val if val is not None else default

    model = _getenv("LOCALCODER_MODEL", "qwen3.6")
    openai_base_url = _getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1")
    openai_api_key = _getenv("OPENAI_API_KEY", "local")
    max_iterations_str = _getenv("LOCALCODER_MAX_ITERATIONS", "40")
    planning_max_iterations_str = _getenv("LOCALCODER_PLANNING_MAX_ITERATIONS", "12")
    logger.info(
        "Loaded agent config: model=%s, openai_base_url=%s, "
        "max_iterations=%s, planning_max_iterations=%s",
        model,
        openai_base_url,
        max_iterations_str,
        planning_max_iterations_str,
    )
    return AgentConfig(
        model=model,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        max_iterations=int(max_iterations_str),
        planning_max_iterations=int(planning_max_iterations_str),
    )
