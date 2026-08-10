"""Process-wide runtime-mutable LLM connection settings.

Lets the desktop app's Settings panel switch between local Ollama,
Tailscale-reachable Ollama, and a hosted OpenRouter API — at runtime,
without a process restart — via a small singleton. Mirrors the
`_registry`/`get_drone_link_registry()` pattern in
aerofleet/hardware/telemetry_service.py and `_fleet_states`/
`get_fleet_state()` in aerofleet/fleet/state.py — the established idiom
in this codebase for process-wide mutable state behind a getter.

Seeded from environment variables on first access so existing
env-var-driven usage (USE_MOCK_AGENTS, OLLAMA_HOST) keeps working
unmodified; a Settings-panel update overrides the seeded value for the
lifetime of the process (or until the next `reload=True`, mirroring
aerofleet.utils.config.get_config(reload=True)).

`CouncilOfExperts()` is instantiated fresh per HTTP request and reads
this singleton via build_llm_backend() on every construction, so a
settings change here takes effect on the very next request — no
additional cache-invalidation needed.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

ConnectionMode = Literal["local_ollama", "tailscale_ollama", "openrouter"]

_VALID_MODES = ("local_ollama", "tailscale_ollama", "openrouter")


@dataclass
class RuntimeLLMSettings:
    mode: ConnectionMode = "local_ollama"
    ollama_host: str = "http://localhost:11434"
    tailscale_host: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model_map: Dict[str, str] = field(default_factory=dict)
    use_mock: bool = False

    def active_ollama_host(self) -> str:
        """The host LocalMissionAgent should actually connect to for the
        current mode — local and Tailscale modes both talk to an
        Ollama-compatible server, differing only in which host."""
        if self.mode == "tailscale_ollama" and self.tailscale_host:
            return self.tailscale_host
        return self.ollama_host

    def to_public_dict(self) -> dict:
        """Settings-panel-safe view — never leaks the raw API key."""
        return {
            "mode": self.mode,
            "ollama_host": self.ollama_host,
            "tailscale_host": self.tailscale_host,
            "has_openrouter_key": bool(self.openrouter_api_key),
            "use_mock": self.use_mock,
        }


_settings: Optional[RuntimeLLMSettings] = None
_lock = threading.Lock()


def _defaults_from_env() -> RuntimeLLMSettings:
    use_mock = os.environ.get("USE_MOCK_AGENTS", "false").lower() in ("1", "true", "yes")
    mode = os.environ.get("AEROFLEET_LLM_MODE", "local_ollama")
    if mode not in _VALID_MODES:
        mode = "local_ollama"
    return RuntimeLLMSettings(
        mode=mode,  # type: ignore[arg-type]
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        tailscale_host=os.environ.get("TAILSCALE_OLLAMA_HOST"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        use_mock=use_mock,
    )


def get_runtime_llm_settings(reload: bool = False) -> RuntimeLLMSettings:
    """Process-wide singleton, lazily seeded from env vars on first access."""
    global _settings
    if _settings is None or reload:
        with _lock:
            if _settings is None or reload:
                _settings = _defaults_from_env()
    return _settings


def update_runtime_llm_settings(**kwargs) -> RuntimeLLMSettings:
    """Applied by the Settings panel's PUT /api/v1/settings/llm endpoint."""
    settings = get_runtime_llm_settings()
    with _lock:
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    return settings
