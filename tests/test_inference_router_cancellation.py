import asyncio

import pytest

from src.llm.inference_router import InferenceRouter, CancelledRequestError


@pytest.mark.asyncio
async def test_generate_honors_cancellation(monkeypatch):
    router = InferenceRouter(mode="local-only")

    async def fake_health():
        return True

    cleanup_called = asyncio.Event()

    async def fake_cleanup():
        cleanup_called.set()

    async def slow_generate(prompt, model, temperature=0.7):
        # Simulate a long-running call that should be cancelled
        await asyncio.sleep(1)
        return "late"

    # Patch methods to avoid real network calls
    monkeypatch.setattr(router, "_check_ollama_health", fake_health)
    monkeypatch.setattr(router, "_cleanup_ollama", fake_cleanup)
    monkeypatch.setattr(router.ollama, "generate", slow_generate)

    cancel_event = asyncio.Event()
    asyncio.get_event_loop().call_later(0.05, cancel_event.set)

    with pytest.raises(CancelledRequestError):
        await router.generate("hello", cancellation_event=cancel_event)

    assert cleanup_called.is_set()


@pytest.mark.asyncio
async def test_generate_completes_without_cancellation(monkeypatch):
    router = InferenceRouter(mode="local-only")

    async def fake_health():
        return True

    async def fast_ollama(
        self, prompt, max_tokens, temperature, cancellation_event=None
    ):
        return "ok"

    monkeypatch.setattr(router, "_check_ollama_health", fake_health)
    monkeypatch.setattr(
        router,
        "_generate_ollama",
        fast_ollama.__get__(router, InferenceRouter),
    )

    result = await router.generate("hi", cancellation_event=asyncio.Event())
    assert result == "ok"
