"""
ModelConfigService: Singleton service for managing model configurations.

Provides centralized access to model assignments, auto-seeding, fallback chains, and validation.
Uses optimized repository for better performance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.db.repositories.optimized_model_config_repository import OptimizedModelConfigRepository

logger = logging.getLogger(__name__)


class ModelConfigService:
    """Singleton service for model configuration management."""

    _instance: Optional[ModelConfigService] = None
    _initialized = False

    def __new__(cls, db: Optional[Any] = None) -> ModelConfigService:
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db: Optional[Any] = None) -> None:
        """Initialize service (only on first call)."""
        if self._initialized:
            return

        if db is None:
            raise ValueError("db client required for initialization")

        self.db = db
        self.repo = OptimizedModelConfigRepository(db)
        self._initialized = True

        # Auto-seed on first init if table is empty
        self._auto_seed_if_empty()
        logger.info("ModelConfigService initialized with optimized repository")

    def get_active_model(self, usage_type: str) -> str:
        """
        Get the first enabled model for a usage type.

        Raises ValueError if no enabled configs exist.
        Uses caching for better performance.
        """
        # Try cache first
        cache_key = f"model_configs:active:{usage_type}"
        if self.db._query_cache:
            try:
                cached = self.db._query_cache._memory_get(cache_key)
                if cached:
                    return cached
            except Exception:
                pass  # Continue without cache
        
        configs = self.repo.get_enabled_by_usage_type(usage_type)
        if not configs:
            raise ValueError(f"No models configured for {usage_type}")
        
        result = configs[0]["model_id"]
        
        # Cache result
        if self.db._query_cache:
            try:
                self.db._query_cache._memory_set(cache_key, result, ttl=300, compressed=False)
            except Exception:
                pass  # Continue without cache
        
        return result

    def get_fallback_chain(self, usage_type: str) -> List[str]:
        """Get ordered list of enabled models for a usage type (for retry logic)."""
        configs = self.repo.get_enabled_by_usage_type(usage_type)
        return [config["model_id"] for config in configs]

    def get_configs_for_usage(self, usage_type: str) -> List[Dict[str, Any]]:
        """Get all configs for a usage type, ordered by priority."""
        return self.repo.get_by_usage_type(usage_type)

    def get_all_configs(self) -> List[Dict[str, Any]]:
        """Get all configurations with caching."""
        cache_key = "model_configs:all"
        if self.db._query_cache:
            try:
                cached = self.db._query_cache._memory_get(cache_key)
                if cached:
                    return cached
            except Exception:
                pass
        
        result = self.repo.get_all()
        
        if self.db._query_cache:
            try:
                self.db._query_cache._memory_set(cache_key, result, ttl=300, compressed=False)
            except Exception:
                pass
        
        return result

    def get_all_configs_grouped(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all configurations grouped by usage_type."""
        all_configs = self.get_all_configs()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for config in all_configs:
            usage_type = config["usage_type"]
            if usage_type not in grouped:
                grouped[usage_type] = []
            grouped[usage_type].append(config)
        return grouped
    
    def get_available_models(self, provider: str = "openrouter") -> List[str]:
        """Get all available model IDs for a provider.
        
        This is the single source of truth for available models.
        Used by enforce_free_tier() and frontend model selection.
        
        Args:
            provider: Provider name (default: openrouter)
            
        Returns:
            List of available model IDs
        """
        all_configs = self.get_all_configs()
        models = set()
        for config in all_configs:
            if config["provider"] == provider and config["enabled"]:
                models.add(config["model_id"])
        return sorted(list(models))

    def upsert_config(
        self,
        usage_type: str,
        priority: int,
        model_id: str,
        model_name: str,
        provider: str,
        parameters: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Upsert a model configuration with cache invalidation."""
        result = self.repo.upsert(
            usage_type=usage_type,
            priority=priority,
            model_id=model_id,
            model_name=model_name,
            provider=provider,
            parameters=parameters,
            enabled=enabled,
        )
        
        # Invalidate cache
        self._invalidate_cache()
        
        return result

    def delete_config(self, usage_type: str, priority: int) -> bool:
        """Delete a specific configuration with cache invalidation."""
        result = self.repo.delete(usage_type, priority)
        if result:
            self._invalidate_cache()
        return result

    def validate_model(self, usage_type: str, model_id: str) -> bool:
        """Validate that a model is configured for a usage type."""
        configs = self.get_configs_for_usage(usage_type)
        for config in configs:
            if config["model_id"] == model_id:
                return True
        return False

    def seed_defaults(self) -> int:
        """Seed default model configurations (idempotent)."""
        defaults = self._get_default_configs()
        return self.repo.seed_defaults(defaults)

    def reset_to_defaults(self) -> int:
        """Clear all configs and re-seed defaults."""
        self.repo.delete_all()
        return self.seed_defaults()

    def _auto_seed_if_empty(self) -> None:
        """Auto-seed defaults if table is empty."""
        if self.repo.is_empty():
            logger.info("Model configs table is empty, auto-seeding defaults")
            self.seed_defaults()
        else:
            logger.info("Model configs table already initialized")

    @staticmethod
    def _get_default_configs() -> List[Dict[str, Any]]:
        """Get default model configurations.
        
        NOTE: Free models are NO LONGER hardcoded. Instead, they should be discovered
        dynamically from OpenRouter's free models API endpoint.
        
        This method now includes only:
        1. Essential fallback models (if OpenRouter discovery fails)
        2. Local Ollama models for embedding and inference
        3. Task-specific model selections
        
        For production: Enable async discovery of free models via OpenRouterModelService
        and seed them into the database on startup.
        """
        configs = []
        
        # NOTE: Free models from OpenRouter should be fetched dynamically via:
        # from src.services.openrouter_model_service import OpenRouterModelService
        # This allows the system to always have the latest 35+ free models without
        # requiring code changes whenever OpenRouter updates their offerings.
        # 
        # For now, we'll add a placeholder usage type for discovered models
        configs.append({
            "usage_type": "general_available_models",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Discover free models dynamically)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Chat Deep (Reasoning-first) - will use openrouter/auto as placeholder
        # Actual models will be discovered and populated dynamically
        configs.append({
            "usage_type": "chat_deep",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Reasoning models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Chat Semantic (Speed-first)
        configs.append({
            "usage_type": "chat_semantic",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Fast models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Chat Text (General purpose)
        configs.append({
            "usage_type": "chat_text",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (General models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Chat Graph (Code/Structure-first)
        configs.append({
            "usage_type": "chat_graph",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Code models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Chat Title (Session naming)
        configs.append({
            "usage_type": "chat_title",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Title models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        # Embedding (Local Ollama)
        configs.append({
            "usage_type": "embedding",
            "priority": 1,
            "model_id": "nomic-embed-text",
            "model_name": "Nomic Embed Text",
            "provider": "ollama",
            "enabled": True,
        })
        
        # Inference (Local Ollama)
        configs.append({
            "usage_type": "inference",
            "priority": 1,
            "model_id": "llama3.1:8b",
            "model_name": "Llama 3.1 8B",
            "provider": "ollama",
            "enabled": True,
        })
        
        # KG Edge Creation (Reasoning)
        configs.append({
            "usage_type": "kg_edge_creation",
            "priority": 1,
            "model_id": "openrouter/auto",
            "model_name": "OpenRouter Auto (Reasoning models discovered at runtime)",
            "provider": "openrouter",
            "enabled": True,
        })
        
        return configs
    
    def _invalidate_cache(self) -> None:
        \"\"\"Invalidate all model config caches.\"\"\"
        if self.db._query_cache:
            try:
                # Invalidate all model config related caches
                self.db._query_cache._memory_delete_pattern(\"model_configs:*\")
                logger.debug(\"Invalidated model config caches\")
            except Exception as e:
                logger.warning(f\"Cache invalidation failed: {e}\")
