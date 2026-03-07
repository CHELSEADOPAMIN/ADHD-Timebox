"""Chat endpoint bridging to Orchestrator."""

from __future__ import annotations

import os
from typing import Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from api.dependencies import get_app_state, get_user_id
from api.errors import error_response
from core.llm_errors import classify_llm_error
from core.events import enqueue_event

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    content: str
    status: str
    agent: str
    tasks_updated: bool
    ascii_art: Optional[str] = None


def _latest_plan_snapshot(plan_dir: str) -> Tuple[Optional[float], Optional[str]]:
    if not plan_dir or not os.path.isdir(plan_dir):
        return None, None
    candidates = [
        name
        for name in os.listdir(plan_dir)
        if name.startswith("daily_tasks_") and name.endswith(".json")
    ]
    if not candidates:
        return None, None
    paths = [os.path.join(plan_dir, name) for name in candidates]
    newest = max(paths, key=lambda p: os.path.getmtime(p))
    return os.path.getmtime(newest), newest


def _extract_ascii_art(content: str) -> Tuple[str, Optional[str]]:
    note = (
        "(SYSTEM NOTE: Please display the ASCII Art reward above verbatim; do not omit it.)"
    )
    if note not in content:
        return content, None

    base = content.split(note)[0].rstrip()
    parts = base.split("\n\n")
    if len(parts) < 2:
        return base, None
    ascii_art = parts[-1].strip("\n")
    main_content = "\n\n".join(parts[:-1]).strip()
    return main_content, ascii_art or None


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, state=Depends(get_app_state), user_id=Depends(get_user_id)):
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")

    message = (payload.message or "").strip()
    if not message:
        return error_response(400, "INVALID_MESSAGE", "message cannot be empty")

    plan_dir = orchestrator.plan_manager.plan_dir
    before_mtime, _ = _latest_plan_snapshot(plan_dir)

    try:
        content = await run_in_threadpool(orchestrator.route, message)
    except Exception as exc:
        classified = classify_llm_error(exc)
        if classified is not None:
            status_code, code, error_message, detail = classified
            return error_response(status_code, code, error_message, detail)
        return error_response(500, "ORCHESTRATOR_ERROR", "Chat processing failed", str(exc))

    after_mtime, newest_path = _latest_plan_snapshot(plan_dir)
    tasks_updated = before_mtime != after_mtime and after_mtime is not None

    status = "CONTINUE" if orchestrator.locked_agent else "FINISHED"
    agent = orchestrator.last_agent or "orchestrator"

    clean_content, ascii_art = _extract_ascii_art(content or "")

    if tasks_updated and newest_path:
        try:
            import json

            from tools.plan_tools_v2 import PlanManager

            plan_date = PlanManager()._plan_date_from_path(newest_path)
            with open(newest_path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            tasks_count = len(tasks) if isinstance(tasks, list) else 0
            enqueue_event(
                state.get_event_queue(user_id),
                state.event_loop,
                {
                    "event": "plan_updated",
                    "data": {
                        "date": plan_date.isoformat(),
                        "tasks_count": tasks_count,
                    },
                },
            )
        except Exception:
            pass

    return ChatResponse(
        content=clean_content or "",
        status=status,
        agent=agent,
        tasks_updated=tasks_updated,
        ascii_art=ascii_art,
    )
