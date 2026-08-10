"""LLM connection settings — the backend half of the desktop Settings
panel's 3-tier connection mode (local Ollama / Tailscale / OpenRouter API).

GET  /api/v1/settings/llm         current settings (API key redacted)
PUT  /api/v1/settings/llm         update mode/host/key
POST /api/v1/settings/llm/test    validate a *proposed* configuration
                                   without saving it
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aerofleet.agents.runtime_settings import (
    ConnectionMode,
    get_runtime_llm_settings,
    update_runtime_llm_settings,
)
from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.data.models.models import User
from aerofleet.utils.exceptions import AgentCommunicationError
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class LLMSettingsUpdate(BaseModel):
    mode: ConnectionMode
    ollama_host: Optional[str] = None
    tailscale_host: Optional[str] = None
    openrouter_api_key: Optional[str] = None


@router.get("/llm")
async def get_llm_settings(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    return get_runtime_llm_settings().to_public_dict()


@router.put("/llm")
async def put_llm_settings(
    body: LLMSettingsUpdate, current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {"mode": body.mode}
    if body.ollama_host is not None:
        updates["ollama_host"] = body.ollama_host
    if body.tailscale_host is not None:
        updates["tailscale_host"] = body.tailscale_host
    if body.openrouter_api_key is not None:
        updates["openrouter_api_key"] = body.openrouter_api_key

    settings = update_runtime_llm_settings(**updates)
    logger.info(f"LLM connection mode switched to {settings.mode}")
    return settings.to_public_dict()


@router.post("/llm/test")
async def test_llm_settings(
    body: LLMSettingsUpdate, current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Build a backend from the *proposed* settings (not yet saved) and try
    to list its models — lets the Settings UI validate before committing."""
    try:
        if body.mode == "openrouter":
            from aerofleet.agents.openrouter_agent import OpenRouterAgent

            backend = OpenRouterAgent(api_key=body.openrouter_api_key)
        else:
            from aerofleet.agents.local_agent import LocalMissionAgent

            host = body.tailscale_host if body.mode == "tailscale_ollama" else body.ollama_host
            # Short timeout — this is a "Test Connection" click, not a real
            # chat call; a bad IP shouldn't hang the Settings UI for a minute.
            backend = LocalMissionAgent(ollama_host_override=host, connect_timeout=5.0)

        models = backend.list_available_models()
        return {"ok": True, "models": models}
    except AgentCommunicationError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
