from unittest import mock
from dataclasses import asdict
from core.agent.config import AgentConfig, load_agent_config


class TestAgentConfigDataclass:
    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "qwen3-coder"
        assert config.planning_model == "qwen3-coder"
        assert config.editing_model == "qwen3-coder"
        assert config.openai_base_url == "http://localhost:11434/v1"
        assert config.openai_api_key == "local"
        assert config.max_iterations == 35
        assert config.planning_max_iterations == 5
        assert config.trivial_max_iterations == 8
        assert config.medium_max_iterations == 18
        assert config.medium_planning_max_iterations == 3
        assert config.llm_temperature == 0.0
        assert config.llm_timeout_seconds == 120.0

    def test_custom_values(self):
        config = AgentConfig(
            model="gpt-4",
            planning_model="gpt-4o-mini",
            editing_model="gpt-4o",
            openai_base_url="https://api.openai.com/v1",
            openai_api_key="sk-test-key",
            max_iterations=100,
            planning_max_iterations=8,
        )
        assert config.model == "gpt-4"
        assert config.planning_model == "gpt-4o-mini"
        assert config.editing_model == "gpt-4o"
        assert config.openai_base_url == "https://api.openai.com/v1"
        assert config.openai_api_key == "sk-test-key"
        assert config.max_iterations == 100
        assert config.planning_max_iterations == 8

    def test_asdict_conversion(self):
        config = AgentConfig(model="claude-3", max_iterations=25)
        d = asdict(config)
        assert isinstance(d, dict)
        assert d["model"] == "claude-3"
        assert d["max_iterations"] == 25


class TestLoadAgentConfig:
    @mock.patch("os.getenv")
    def test_load_with_env_vars(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default: {
            "LOCALCODER_MODEL": "mistral-large",
            "LOCALCODER_PLANNING_MODEL": "small-planner",
            "LOCALCODER_EDITING_MODEL": "big-editor",
            "OPENAI_API_BASE_URL": "http://custom.host:9000/v1",
            "OPENAI_API_KEY": "env-key-123",
            "LOCALCODER_MAX_ITERATIONS": "75",
            "LOCALCODER_PLANNING_MAX_ITERATIONS": "9",
            "LOCALCODER_TRIVIAL_MAX_ITERATIONS": "6",
            "LOCALCODER_MEDIUM_MAX_ITERATIONS": "15",
            "LOCALCODER_MEDIUM_PLANNING_MAX_ITERATIONS": "1",
        }.get(key, default)

        config = load_agent_config()
        assert config.model == "mistral-large"
        assert config.planning_model == "small-planner"
        assert config.editing_model == "big-editor"
        assert config.openai_base_url == "http://custom.host:9000/v1"
        assert config.openai_api_key == "env-key-123"
        assert config.max_iterations == 75
        assert config.planning_max_iterations == 9
        assert config.trivial_max_iterations == 6
        assert config.medium_max_iterations == 15
        assert config.medium_planning_max_iterations == 1

    @mock.patch("os.getenv")
    def test_load_with_defaults(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default: default

        config = load_agent_config()
        assert config.model == "qwen3-coder"
        assert config.openai_base_url == "http://localhost:11434/v1"
        assert config.openai_api_key == "local"
        assert config.max_iterations == 35
        assert config.planning_max_iterations == 5
        assert config.medium_max_iterations == 18
        assert config.medium_planning_max_iterations == 3

    @mock.patch("os.getenv")
    def test_max_iterations_converted_to_int(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default: {
            "LOCALCODER_MAX_ITERATIONS": "99",
        }.get(key, default)

        config = load_agent_config()
        assert isinstance(config.max_iterations, int)
        assert config.max_iterations == 99
