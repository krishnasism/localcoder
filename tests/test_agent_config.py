from unittest import mock
from dataclasses import asdict
from core.agent.config import AgentConfig, load_agent_config


class TestAgentConfigDataclass:
    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "qwen3.6"
        assert config.openai_base_url == "http://localhost:11434/v1"
        assert config.openai_api_key == "local"
        assert config.max_iterations == 25
        assert config.planning_max_iterations == 5

    def test_custom_values(self):
        config = AgentConfig(
            model="gpt-4",
            openai_base_url="https://api.openai.com/v1",
            openai_api_key="sk-test-key",
            max_iterations=100,
            planning_max_iterations=8,
        )
        assert config.model == "gpt-4"
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
            "OPENAI_API_BASE_URL": "http://custom.host:9000/v1",
            "OPENAI_API_KEY": "env-key-123",
            "LOCALCODER_MAX_ITERATIONS": "75",
            "LOCALCODER_PLANNING_MAX_ITERATIONS": "9",
        }.get(key, default)

        config = load_agent_config()
        assert config.model == "mistral-large"
        assert config.openai_base_url == "http://custom.host:9000/v1"
        assert config.openai_api_key == "env-key-123"
        assert config.max_iterations == 75
        assert config.planning_max_iterations == 9

    @mock.patch("os.getenv")
    def test_load_with_defaults(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default: default

        config = load_agent_config()
        assert config.model == "qwen3.6"
        assert config.openai_base_url == "http://localhost:11434/v1"
        assert config.openai_api_key == "local"
        assert config.max_iterations == 25
        assert config.planning_max_iterations == 5

    @mock.patch("os.getenv")
    def test_max_iterations_converted_to_int(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default: {
            "LOCALCODER_MAX_ITERATIONS": "99",
        }.get(key, default)

        config = load_agent_config()
        assert isinstance(config.max_iterations, int)
        assert config.max_iterations == 99
