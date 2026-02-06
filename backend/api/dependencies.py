"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from core.state import app_state, AppState


def get_app_state() -> AppState:
    return app_state


def get_user_id(request: Request) -> str:
    # Desktop app runs single-user mode.
    return "default-user"
