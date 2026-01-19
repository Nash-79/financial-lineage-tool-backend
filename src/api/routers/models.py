"""
API router for unified model configuration endpoints.

Provides REST API for managing model configurations, discovering available models,
and seeding default configurations.
"""

from __future__ import annotations

import logging
from typing import Any, List

from fastapi import APIRouter, HTTPException, status
from starlette.responses import JSONResponse

import httpx

from src.api.schemas.models import (
    AllModelsResponse,
    ChatModeStatus,
    ErrorResponse,
    ModelAvailabilityResponse,
    ModelConfigGrouped,
    ModelConfigResponse,
    ModelConfigRequest,
    ModelConfigRequest as ConfigRequest,
    ModelConfigRequest as Request,
    OllamaModelsResponse,
    OpenRouterModelsResponse,
    ProviderStatus,
    SeedDefaultsRequest,
    UsageType,
)
from src.services.cached_model_config_service import CachedModelConfigService
from src.services.ollama_model_service import OllamaModelService
from src.services.openrouter_model_service import OpenRouterModelService
from src.storage.duckdb_client import get_duckdb_client
from src.storage.dependency_injection import ServiceContainer, get_service_container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _get_model_config_service() -> CachedModelConfigService:
    """Get or create CachedModelConfigService with Redis integration."""
    try:
        # Try to get Redis client from config
        redis_client = None
        try:
            from src.api.config import config

            if hasattr(config, "REDIS_URL") and config.REDIS_URL:
                import redis.asyncio as redis

                redis_client = redis.from_url(config.REDIS_URL)
        except Exception:
            # Redis not configured, will use in-memory cache fallback
            pass

        # Use dependency injection container
        db = get_duckdb_client()
        cache = None
        if redis_client:
            from src.storage.query_cache import QueryCache

            cache = QueryCache(redis_client=redis_client)

        return CachedModelConfigService(db, cache)
    except Exception as e:
        logger.error(f"Failed to initialize CachedModelConfigService: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model configuration service unavailable",
        )


@router.get(
    "/openrouter/free",
    response_model=OpenRouterModelsResponse,
    summary="List free OpenRouter models",
    description="Fetch available free models from OpenRouter API. Returns cached results if available.",
)
async def get_openrouter_free_models() -> OpenRouterModelsResponse:
    """Get available free models from OpenRouter with Redis caching."""
    try:
        from src.api.config import config

        # Set up Redis client for caching
        redis_client = None
        try:
            if hasattr(config, "REDIS_URL") and config.REDIS_URL:
                import redis.asyncio as redis

                redis_client = redis.from_url(config.REDIS_URL)
        except Exception:
            pass

        service = OpenRouterModelService(
            api_key=config.OPENROUTER_API_KEY,
            redis_client=redis_client,
        )
        models = await service.fetch_free_models()

        return OpenRouterModelsResponse(
            models=models,
            cached=redis_client is not None,  # Indicate if Redis was used
        )
    except Exception as e:
        logger.error(f"Failed to fetch OpenRouter models: {e}")
        # Return empty list instead of error (graceful degradation)
        return OpenRouterModelsResponse(models=[])


@router.get(
    "/ollama",
    response_model=OllamaModelsResponse,
    summary="List available Ollama models",
    description="Fetch available local Ollama models from the configured Ollama instance.",
)
async def get_ollama_models() -> OllamaModelsResponse:
    """Get available Ollama models with Redis caching."""
    try:
        from src.api.config import config

        # Set up Redis client for caching (Ollama service may use it internally)
        redis_client = None
        try:
            if hasattr(config, "REDIS_URL") and getattr(config, "REDIS_URL", None):
                import redis.asyncio as redis

                redis_client = redis.from_url(config.REDIS_URL)
        except Exception:
            pass

        service = OllamaModelService(ollama_host=config.OLLAMA_HOST)
        models = await service.fetch_available_models()

        return OllamaModelsResponse(models=models)
    except Exception as e:
        logger.error(f"Failed to fetch Ollama models: {e}")
        # Return empty list instead of error (graceful degradation)
        return OllamaModelsResponse(models=[])


@router.get(
    "/config",
    response_model=AllModelsResponse,
    summary="Get all model configurations",
    description="Returns all model configurations grouped by usage type.",
)
async def get_all_model_configs() -> AllModelsResponse:
    """Get all model configurations grouped by usage type."""
    try:
        service = _get_model_config_service()
        grouped = service.get_all_configs_grouped()

        result: List[ModelConfigGrouped] = []
        for usage_type, configs in grouped.items():
            result.append(
                ModelConfigGrouped(
                    usage_type=usage_type,
                    configs=[
                        ModelConfigResponse(
                            id=config["id"],
                            usage_type=config["usage_type"],
                            priority=config["priority"],
                            model_id=config["model_id"],
                            model_name=config["model_name"],
                            provider=config["provider"],
                            parameters=config.get("parameters") if isinstance(config.get("parameters"), dict) else ({} if config.get("parameters") else None),
                            enabled=config["enabled"],
                            created_at=str(config.get("created_at")) if config.get("created_at") else None,
                            updated_at=str(config.get("updated_at")) if config.get("updated_at") else None,
                        )
                        for config in configs
                    ],
                )
            )

        return AllModelsResponse(grouped_by_usage_type=result)
    except Exception as e:
        logger.error(f"Failed to get model configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve model configurations",
        )


@router.post(
    "/config",
    response_model=ModelConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update model configuration",
    description="Upsert (create or update) a model configuration. Idempotent operation.",
)
async def upsert_model_config(request: ModelConfigRequest) -> ModelConfigResponse:
    """Upsert a model configuration."""
    try:
        service = _get_model_config_service()

        # Validate usage_type
        if request.usage_type not in [e.value for e in UsageType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid usage_type: {request.usage_type}",
            )

        # Validate priority
        if request.priority < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Priority must be >= 1",
            )

        config = service.upsert_config(
            usage_type=request.usage_type,
            priority=request.priority,
            model_id=request.model_id,
            model_name=request.model_name,
            provider=request.provider,
            parameters=request.parameters,
            enabled=request.enabled,
        )

        return ModelConfigResponse(
            id=config["id"],
            usage_type=config["usage_type"],
            priority=config["priority"],
            model_id=config["model_id"],
            model_name=config["model_name"],
            provider=config["provider"],
            parameters=config.get("parameters"),
            enabled=config["enabled"],
            created_at=str(config.get("created_at")),
            updated_at=str(config.get("updated_at")),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert model configuration",
        )


@router.delete(
    "/config/{usage_type}/{priority}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete model configuration",
    description="Remove a specific model configuration by usage_type and priority.",
)
async def delete_model_config(usage_type: str, priority: int) -> None:
    """Delete a model configuration."""
    try:
        service = _get_model_config_service()

        # Validate usage_type
        if usage_type not in [e.value for e in UsageType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid usage_type: {usage_type}",
            )

        # Validate priority
        if priority < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Priority must be >= 1",
            )

        service.delete_config(usage_type, priority)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model configuration",
        )


@router.post(
    "/config/seed",
    status_code=status.HTTP_200_OK,
    summary="Seed default model configurations",
    description="Seed or reset to default model configurations. Idempotent operation.",
)
async def seed_default_configs(request: SeedDefaultsRequest = None) -> dict:
    """Seed default model configurations."""
    try:
        service = _get_model_config_service()

        if request and request.override:
            # Reset to defaults
            count = service.reset_to_defaults()
            logger.info(f"Reset model configs to defaults, seeded {count} configs")
            return {
                "message": "Model configurations reset to defaults",
                "configs_seeded": count,
            }
        else:
            # Just seed (idempotent)
            count = service.seed_defaults()
            logger.info(f"Seeded {count} default model configurations")
            return {
                "message": "Default model configurations seeded",
                "configs_seeded": count,
            }
    except Exception as e:
        logger.error(f"Failed to seed model configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed model configurations",
        )


@router.get(
    "/health",
    summary="Check model configuration service health",
    description="Health check endpoint for model configuration service.",
)
async def health_check() -> dict:
    """Check health of model configuration service."""
    try:
        service = _get_model_config_service()
        configs = service.get_all_configs()
        return {
            "status": "healthy",
            "total_configs": len(configs),
            "message": "Model configuration service is operational",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "message": "Model configuration service is unavailable",
            },
        )


@router.get(
    "/availability",
    response_model=ModelAvailabilityResponse,
    summary="Get model availability by chat mode",
    description="Returns per-chat-mode readiness status based on configuration and provider availability.",
)
async def get_model_availability() -> ModelAvailabilityResponse:
    """Get model availability status for all chat modes."""
    from src.api.config import config

    # Required usage types for chat modes
    chat_mode_usage_types = {
        "deep": "chat_deep",
        "semantic": "chat_semantic",
        "graph": "chat_graph",
        "text": "chat_text",
    }

    all_required_usage_types = [
        "chat_deep", "chat_graph", "chat_semantic", "chat_text",
        "chat_title", "embedding", "inference", "kg_edge_creation"
    ]

    # Check provider availability
    providers = {}

    # Check Ollama
    ollama_online = False
    ollama_model_count = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            if r.status_code == 200:
                ollama_online = True
                data = r.json()
                ollama_model_count = len(data.get("models", []))
    except Exception as e:
        logger.debug(f"Ollama check failed: {e}")

    providers["ollama"] = ProviderStatus(
        status="online" if ollama_online else "offline",
        model_count=ollama_model_count if ollama_online else None,
        message=None if ollama_online else "Cannot connect to Ollama",
    )

    # Check OpenRouter
    openrouter_configured = bool(config.OPENROUTER_API_KEY)
    providers["openrouter"] = ProviderStatus(
        status="configured" if openrouter_configured else "missing",
        model_count=None,  # Would need API call to get count
        message=None if openrouter_configured else "API key not configured",
    )

    # Get model configurations
    try:
        service = _get_model_config_service()
        grouped = service.get_all_configs_grouped()
        configured_types = list(grouped.keys())
    except Exception as e:
        logger.error(f"Failed to get model configs for availability: {e}")
        grouped = {}
        configured_types = []

    missing_types = [ut for ut in all_required_usage_types if ut not in configured_types]

    # Determine chat mode status
    chat_modes = {}
    for mode_name, usage_type in chat_mode_usage_types.items():
        configs = grouped.get(usage_type, [])
        is_configured = len(configs) > 0

        if not is_configured:
            chat_modes[mode_name] = ChatModeStatus(
                status="unavailable",
                reason=f"No model configured for {usage_type}",
                configured=False,
                provider=None,
            )
            continue

        # Get primary config (priority 1 or lowest priority)
        primary_config = min(configs, key=lambda c: c.get("priority", 999))
        provider = primary_config.get("provider", "unknown")

        # Check if provider is available
        provider_available = False
        if provider == "ollama":
            provider_available = ollama_online
        elif provider == "openrouter":
            provider_available = openrouter_configured

        if provider_available:
            chat_modes[mode_name] = ChatModeStatus(
                status="ready",
                reason=None,
                configured=True,
                provider=provider,
            )
        else:
            # Check for fallback
            has_fallback = len(configs) > 1
            fallback_available = False
            if has_fallback:
                for cfg in configs:
                    if cfg.get("provider") != provider:
                        fallback_provider = cfg.get("provider")
                        if fallback_provider == "ollama" and ollama_online:
                            fallback_available = True
                            break
                        elif fallback_provider == "openrouter" and openrouter_configured:
                            fallback_available = True
                            break

            if fallback_available:
                chat_modes[mode_name] = ChatModeStatus(
                    status="degraded",
                    reason=f"Primary provider ({provider}) offline, using fallback",
                    configured=True,
                    provider=provider,
                )
            else:
                chat_modes[mode_name] = ChatModeStatus(
                    status="unavailable",
                    reason=f"Provider ({provider}) is offline",
                    configured=True,
                    provider=provider,
                )

    return ModelAvailabilityResponse(
        chat_modes=chat_modes,
        providers=providers,
        configured_usage_types=configured_types,
        missing_usage_types=missing_types,
    )
