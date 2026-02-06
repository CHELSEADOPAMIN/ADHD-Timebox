"""OpenOnion Google OAuth helpers."""

from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from dotenv import load_dotenv, set_key

from agents.orchestrator import OrchestratorAgent


class OAuthError(RuntimeError):
    pass


def _base_url() -> str:
    return (
        os.getenv("OPENONION_BACKEND_URL")
        or os.getenv("OPENONION_BASE_URL")
        or "https://oo.openonion.ai"
    ).rstrip("/")


def _api_key() -> str:
    api_key = os.getenv("OPENONION_API_KEY")
    if not api_key:
        raise OAuthError("OPENONION_API_KEY is not set")
    return api_key


def _request_json(method: str, path: str, payload: Optional[dict] = None) -> Dict[str, Any]:
    url = f"{_base_url()}{path}"
    headers = {"Authorization": f"Bearer {_api_key()}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise OAuthError(f"OpenOnion request failed: {exc.code} {body}")
    except urllib.error.URLError as exc:
        raise OAuthError(f"OpenOnion network error: {exc.reason}")

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise OAuthError(f"OpenOnion response parse failed: {exc}")


def init_google_oauth() -> Dict[str, Any]:
    return _request_json("GET", "/api/v1/oauth/google/init")


def poll_google_status() -> Dict[str, Any]:
    return _request_json("GET", "/api/v1/oauth/google/status")


def fetch_google_credentials() -> Dict[str, Any]:
    return _request_json("GET", "/api/v1/oauth/google/credentials")


def _normalize_scopes(scopes: Any) -> str:
    if scopes is None:
        return ""
    if isinstance(scopes, list):
        return " ".join(scopes)
    return str(scopes)


def save_google_credentials(credentials: Dict[str, Any], env_path: str) -> None:
    access_token = credentials.get("access_token") or ""
    refresh_token = credentials.get("refresh_token") or ""
    expires_at = credentials.get("expires_at") or credentials.get("expires_at_utc") or ""
    scopes = _normalize_scopes(credentials.get("scopes"))
    email = credentials.get("google_email") or credentials.get("email") or ""

    set_key(env_path, "GOOGLE_ACCESS_TOKEN", access_token)
    set_key(env_path, "GOOGLE_REFRESH_TOKEN", refresh_token)
    if expires_at:
        set_key(env_path, "GOOGLE_TOKEN_EXPIRES_AT", str(expires_at))
    if scopes:
        set_key(env_path, "GOOGLE_SCOPES", scopes)
    if email:
        set_key(env_path, "GOOGLE_EMAIL", email)

    os.environ["GOOGLE_ACCESS_TOKEN"] = access_token
    os.environ["GOOGLE_REFRESH_TOKEN"] = refresh_token
    if expires_at:
        os.environ["GOOGLE_TOKEN_EXPIRES_AT"] = str(expires_at)
    if scopes:
        os.environ["GOOGLE_SCOPES"] = scopes
    if email:
        os.environ["GOOGLE_EMAIL"] = email


def refresh_calendar(orchestrator: OrchestratorAgent) -> None:
    from connectonion import GoogleCalendar

    calendar = GoogleCalendar()
    orchestrator.plan_manager.calendar = calendar
    orchestrator.planner_agent.calendar = calendar
    orchestrator.planner_agent.plan_manager.calendar = calendar


def apply_google_oauth(orchestrator: OrchestratorAgent, env_path: str) -> Dict[str, Any]:
    credentials = fetch_google_credentials()
    save_google_credentials(credentials, env_path)
    load_dotenv(env_path, override=True)
    refresh_calendar(orchestrator)
    return credentials


def is_connected() -> bool:
    access = os.getenv("GOOGLE_ACCESS_TOKEN")
    refresh = os.getenv("GOOGLE_REFRESH_TOKEN")
    scopes = os.getenv("GOOGLE_SCOPES", "")
    if not access or not refresh:
        return False
    return "calendar" in scopes


def get_token_expiry() -> Optional[datetime.datetime]:
    expires_at = os.getenv("GOOGLE_TOKEN_EXPIRES_AT")
    if not expires_at:
        return None
    try:
        return datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception:
        return None
