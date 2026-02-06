"""Calendar sync and export endpoints."""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, Optional

from dotenv import unset_key
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from api.dependencies import get_app_state, get_user_id
from api.errors import error_response
from core.oauth import OAuthError, init_google_oauth
from tools.ics_tools import build_ics

router = APIRouter()


def _google_status_payload() -> Dict[str, Any]:
    access = os.getenv("GOOGLE_ACCESS_TOKEN")
    refresh = os.getenv("GOOGLE_REFRESH_TOKEN")
    scopes = os.getenv("GOOGLE_SCOPES", "")
    email = os.getenv("GOOGLE_EMAIL", "")
    expires_at = os.getenv("GOOGLE_TOKEN_EXPIRES_AT", "")

    if not access or not refresh:
        return {
            "connected": False,
            "message": "Google Calendar is not connected.",
        }

    try:
        from connectonion import GoogleCalendar

        _ = GoogleCalendar()
    except Exception as exc:
        return {
            "connected": False,
            "message": "Google Calendar is not authorized or unavailable.",
            "detail": str(exc),
        }

    return {
        "connected": True,
        "email": email or None,
        "scopes": scopes or None,
        "expires_at": expires_at or None,
    }


@router.get("/api/calendar/status")
async def calendar_status(state=Depends(get_app_state), user_id=Depends(get_user_id)):
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")

    plan_manager = orchestrator.plan_manager
    status = _google_status_payload()

    last_sync_time = getattr(plan_manager, "last_sync_time", None)
    last_sync_summary = getattr(plan_manager, "last_sync_summary", None)

    return {
        "connected": status.get("connected", False),
        "email": status.get("email"),
        "expires_at": status.get("expires_at"),
        "message": status.get("message"),
        "detail": status.get("detail"),
        "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
        "last_sync_summary": last_sync_summary,
    }


@router.get("/api/calendar/ics")
async def calendar_ics(
    date: Optional[str] = Query(None),
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")

    plan_manager = orchestrator.plan_manager
    today = datetime.date.today()
    plan_date, date_err = plan_manager._parse_plan_date(date, today)
    if date_err:
        return error_response(400, "INVALID_DATE", "Invalid date format", date_err)

    tasks, path, err = plan_manager._load_tasks(plan_date.isoformat(), False)
    if err:
        return error_response(404, "PLAN_NOT_FOUND", "Plan file not found", err)

    content = build_ics(tasks or [], plan_date)
    filename = f"timebox_{plan_date.isoformat()}.ics"
    return Response(
        content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/calendar/sync")
async def calendar_sync(
    date: Optional[str] = Query(None),
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")

    plan_manager = orchestrator.plan_manager
    result = plan_manager.sync_plan_date(date)
    if result.get("error"):
        return error_response(
            result.get("status", 500),
            result.get("code", "SYNC_FAILED"),
            result.get("message", "Calendar sync failed"),
            result.get("detail"),
        )

    return result


@router.post("/api/calendar/connect")
async def calendar_connect():
    try:
        data = init_google_oauth()
    except OAuthError as exc:
        return error_response(502, "OAUTH_INIT_FAILED", "OAuth init failed", str(exc))

    auth_url = data.get("auth_url") or data.get("url")
    if not auth_url:
        return error_response(502, "OAUTH_INIT_FAILED", "No authorization URL returned")

    return {
        "auth_url": auth_url,
        "poll_endpoint": "/api/auth/google/status",
        "timeout_seconds": 300,
    }


@router.post("/api/calendar/disconnect")
async def calendar_disconnect(state=Depends(get_app_state), user_id=Depends(get_user_id)):
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")

    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.abspath(env_path)
    for key in (
        "GOOGLE_ACCESS_TOKEN",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_TOKEN_EXPIRES_AT",
        "GOOGLE_SCOPES",
        "GOOGLE_EMAIL",
    ):
        try:
            unset_key(env_path, key)
        except Exception:
            pass
        os.environ.pop(key, None)

    orchestrator.plan_manager.calendar = None
    orchestrator.planner_agent.calendar = None
    orchestrator.planner_agent.plan_manager.calendar = None

    return {"connected": False, "message": "Google Calendar disconnected."}
