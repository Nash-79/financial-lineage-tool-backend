"""Unit tests for chat endpoint model routing configuration."""

import pytest
from unittest.mock import patch


class TestChatModelRouting:
    """Test suite for chat endpoint model routing configuration."""

    @pytest.fixture
    def config(self):
        """Get fresh config instance."""
        # Re-import to get fresh config
        from src.api.config import LocalConfig
        return LocalConfig

    def test_free_tier_models_includes_qwen(self, config):
        """Test that qwen/qwen3-4b:free is in the free-tier models list."""
        assert "qwen/qwen3-4b:free" in config._DEFAULT_FREE_TIER_MODELS

    def test_free_tier_models_count(self, config):
        """Test that all expected free-tier models are present."""
        expected_models = [
            "google/gemini-2.0-flash-exp:free",
            "mistralai/mistral-7b-instruct:free",
            "mistralai/devstral-2512:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "deepseek/deepseek-r1-0528:free",
            "qwen/qwen3-4b:free",
        ]
        for model in expected_models:
            assert model in config._DEFAULT_FREE_TIER_MODELS, f"{model} missing from free-tier list"

    def test_deep_endpoint_routing_order(self, config):
        """Test /deep endpoint uses reasoning-first routing."""
        # Primary: DeepSeek R1 (reasoning/CoT)
        assert config.CHAT_DEEP_PRIMARY_MODEL == "deepseek/deepseek-r1-0528:free"
        # Secondary: Devstral (code-aware fallback)
        assert config.CHAT_DEEP_SECONDARY_MODEL == "mistralai/devstral-2512:free"
        # Tertiary: Gemini (fast general fallback)
        assert config.CHAT_DEEP_TERTIARY_MODEL == "google/gemini-2.0-flash-exp:free"

    def test_graph_endpoint_routing_order(self, config):
        """Test /graph endpoint uses code/structure-first routing."""
        # Primary: Devstral (code/structure specialist)
        assert config.CHAT_GRAPH_PRIMARY_MODEL == "mistralai/devstral-2512:free"
        # Secondary: DeepSeek R1 (reasoning fallback)
        assert config.CHAT_GRAPH_SECONDARY_MODEL == "deepseek/deepseek-r1-0528:free"
        # Tertiary: Gemini (fast fallback)
        assert config.CHAT_GRAPH_TERTIARY_MODEL == "google/gemini-2.0-flash-exp:free"

    def test_semantic_endpoint_routing_order(self, config):
        """Test /semantic endpoint uses speed-first routing."""
        # Primary: Gemini (fastest)
        assert config.CHAT_SEMANTIC_PRIMARY_MODEL == "google/gemini-2.0-flash-exp:free"
        # Secondary: Qwen (fast, efficient)
        assert config.CHAT_SEMANTIC_SECONDARY_MODEL == "qwen/qwen3-4b:free"
        # Tertiary: Mistral 7B (balanced fallback)
        assert config.CHAT_SEMANTIC_TERTIARY_MODEL == "mistralai/mistral-7b-instruct:free"

    def test_text_endpoint_routing_order(self, config):
        """Test /text endpoint uses speed-first routing."""
        # Primary: Gemini (fastest, no-RAG friendly)
        assert config.CHAT_TEXT_PRIMARY_MODEL == "google/gemini-2.0-flash-exp:free"
        # Secondary: Mistral 7B (balanced chat)
        assert config.CHAT_TEXT_SECONDARY_MODEL == "mistralai/mistral-7b-instruct:free"
        # Tertiary: Qwen (efficient fallback)
        assert config.CHAT_TEXT_TERTIARY_MODEL == "qwen/qwen3-4b:free"

    def test_get_chat_endpoint_models_returns_all_endpoints(self, config):
        """Test that get_chat_endpoint_models returns configuration for all endpoints."""
        models = config.get_chat_endpoint_models()

        expected_endpoints = [
            "/api/chat/deep",
            "/api/chat/graph",
            "/api/chat/semantic",
            "/api/chat/text",
            "/api/chat/title",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in models, f"{endpoint} missing from model configuration"
            assert "primary" in models[endpoint]
            assert "secondary" in models[endpoint]
            assert "tertiary" in models[endpoint]

    def test_chat_artifact_retention_days_default(self, config):
        """Test that CHAT_ARTIFACT_RETENTION_DAYS has correct default."""
        assert config.CHAT_ARTIFACT_RETENTION_DAYS == 90

    def test_chat_artifact_retention_days_env_override(self):
        """Test that CHAT_ARTIFACT_RETENTION_DAYS can be overridden via env."""
        import os

        with patch.dict(os.environ, {"CHAT_ARTIFACT_RETENTION_DAYS": "30"}):
            # Re-import to pick up new env value
            import importlib
            import src.api.config as config_module
            importlib.reload(config_module)

            assert config_module.LocalConfig.CHAT_ARTIFACT_RETENTION_DAYS == 30

            # Restore
            importlib.reload(config_module)


class TestFreeTierEnforcement:
    """Test suite for free-tier model enforcement."""

    def test_enforce_free_tier_returns_model_if_in_whitelist(self):
        """Test that whitelisted models are returned as-is."""
        from src.llm.free_tier import enforce_free_tier

        model, downgraded = enforce_free_tier("google/gemini-2.0-flash-exp:free")
        assert model == "google/gemini-2.0-flash-exp:free"
        assert downgraded is False

    def test_enforce_free_tier_returns_model_if_qwen_in_whitelist(self):
        """Test that qwen model is returned as-is when in whitelist."""
        from src.llm.free_tier import enforce_free_tier

        model, downgraded = enforce_free_tier("qwen/qwen3-4b:free")
        assert model == "qwen/qwen3-4b:free"
        assert downgraded is False

    def test_enforce_free_tier_downgrades_non_free_model(self):
        """Test that non-free models are downgraded."""
        from src.llm.free_tier import enforce_free_tier, DEFAULT_FREE_TIER_MODEL

        model, downgraded = enforce_free_tier("openai/gpt-4o")
        assert model == DEFAULT_FREE_TIER_MODEL
        assert downgraded is True

    def test_enforce_free_tier_handles_none(self):
        """Test that None model returns default."""
        from src.llm.free_tier import enforce_free_tier, DEFAULT_FREE_TIER_MODEL

        model, downgraded = enforce_free_tier(None)
        assert model == DEFAULT_FREE_TIER_MODEL
        assert downgraded is False

    def test_enforce_free_tier_handles_empty_string(self):
        """Test that empty string model returns default."""
        from src.llm.free_tier import enforce_free_tier, DEFAULT_FREE_TIER_MODEL

        model, downgraded = enforce_free_tier("")
        assert model == DEFAULT_FREE_TIER_MODEL
        assert downgraded is False
