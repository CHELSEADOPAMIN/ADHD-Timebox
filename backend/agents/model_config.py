"""Shared model selection helper."""

from __future__ import annotations

import os
from typing import Optional


def resolve_model(model: Optional[str] = None) -> str:
    if model:
        return model

    env_model = os.getenv("DEFAULT_MODEL") or os.getenv("LLM_MODEL")
    if env_model:
        return env_model

    if os.getenv("OPENONION_API_KEY"):
        return "co/gemini-2.5-pro"
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if os.getenv("OPENAI_API_KEY"):
        return "gpt-4o"

    return "co/gemini-2.5-pro"
