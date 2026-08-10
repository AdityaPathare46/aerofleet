"""LLM backend selection — mock, local/Tailscale Ollama, or OpenRouter API.

Shared by council.py and base_agent.py so both pick the same backend
without importing each other.
"""
from aerofleet.agents.runtime_settings import get_runtime_llm_settings


def build_llm_backend():
    """Select a backend based on the current RuntimeLLMSettings — mock
    (explicit override, always wins), local/Tailscale Ollama (same class,
    differing only in host), or OpenRouter API."""
    settings = get_runtime_llm_settings()

    if settings.use_mock:
        from aerofleet.agents.mock_agent import MockLLMBackend
        return MockLLMBackend()

    if settings.mode == "openrouter":
        from aerofleet.agents.openrouter_agent import OpenRouterAgent
        return OpenRouterAgent(
            api_key=settings.openrouter_api_key,
            model_map=settings.openrouter_model_map,
        )

    from aerofleet.agents.local_agent import LocalMissionAgent
    return LocalMissionAgent(ollama_host_override=settings.active_ollama_host())
