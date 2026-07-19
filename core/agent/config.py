import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    model: str = "qwen3-coder"
    planning_model: str = "qwen3-coder"  # TODO: Need to research a nicer model for planning
    editing_model: str = "qwen3-coder"
    openai_base_url: str = "http://localhost:11434/v1"
    openai_api_key: str = "local"
    max_iterations: int = 35
    planning_max_iterations: int = 5
    trivial_max_iterations: int = 8
    medium_max_iterations: int = 18
    medium_planning_max_iterations: int = 3
    snapshot_cache_ttl_seconds: float = 45.0
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 120.0


def load_agent_config() -> AgentConfig:
    def _getenv(key: str, default: str) -> str:
        val = os.getenv(key, default)
        return val if val is not None else default

    model = _getenv("LOCALCODER_MODEL", "qwen3-coder")
    planning_model = _getenv("LOCALCODER_PLANNING_MODEL", "")
    editing_model = _getenv("LOCALCODER_EDITING_MODEL", "")
    openai_base_url = _getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1")
    openai_api_key = _getenv("OPENAI_API_KEY", "local")
    max_iterations_str = _getenv("LOCALCODER_MAX_ITERATIONS", "35")
    planning_max_iterations_str = _getenv("LOCALCODER_PLANNING_MAX_ITERATIONS", "5")
    trivial_max_iterations_str = _getenv("LOCALCODER_TRIVIAL_MAX_ITERATIONS", "8")
    medium_max_iterations_str = _getenv("LOCALCODER_MEDIUM_MAX_ITERATIONS", "18")
    medium_planning_max_iterations_str = _getenv(
        "LOCALCODER_MEDIUM_PLANNING_MAX_ITERATIONS", "3"
    )
    snapshot_cache_ttl_str = _getenv("LOCALCODER_SNAPSHOT_CACHE_TTL", "45")
    llm_temperature_str = _getenv("LOCALCODER_LLM_TEMPERATURE", "0")
    llm_timeout_str = _getenv("LOCALCODER_LLM_TIMEOUT", "120")
    logger.info(
        "Loaded agent config: model=%s, planning_model=%s, editing_model=%s, "
        "openai_base_url=%s, max_iterations=%s, planning_max_iterations=%s, "
        "trivial_max_iterations=%s, medium_max_iterations=%s",
        model,
        planning_model or model,
        editing_model or model,
        openai_base_url,
        max_iterations_str,
        planning_max_iterations_str,
        trivial_max_iterations_str,
        medium_max_iterations_str,
    )
    return AgentConfig(
        model=model,
        planning_model=planning_model,
        editing_model=editing_model,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        max_iterations=int(max_iterations_str),
        planning_max_iterations=int(planning_max_iterations_str),
        trivial_max_iterations=int(trivial_max_iterations_str),
        medium_max_iterations=int(medium_max_iterations_str),
        medium_planning_max_iterations=int(medium_planning_max_iterations_str),
        snapshot_cache_ttl_seconds=float(snapshot_cache_ttl_str),
        llm_temperature=float(llm_temperature_str),
        llm_timeout_seconds=float(llm_timeout_str),
    )
