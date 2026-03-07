"""Focus session management API.
 
This module implements the focus session state machine with full lifecycle management:
- Session creation and control (start/pause/resume/abandon)
- Automatic session completion
- Session history tracking
- SSE event notifications for state changes
"""
 
from __future__ import annotations
 
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
 
from api.dependencies import get_app_state, get_user_id
from api.errors import error_response
from core.events import enqueue_event
 
router = APIRouter()
 
 
# =============================================================================
# Data Models
# =============================================================================
 
class SessionStartRequest(BaseModel):
    """Request to start a new focus session."""
    task_id: Optional[str] = None
    duration_minutes: int = 25
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-123",
                "duration_minutes": 25
            }
        }
 
 
class SessionPauseRequest(BaseModel):
    """Request to pause a focus session."""
    reason: Optional[str] = None
 
 
class SessionAbandonRequest(BaseModel):
    """Request to abandon a focus session."""
    reason: Optional[str] = None
 
 
class SessionHistoryEntry(BaseModel):
    """A completed or abandoned session in history."""
    id: str
    date: str
    task_id: Optional[str]
    task_title: Optional[str]
    duration_minutes: int
    actual_minutes: int
    outcome: "completed" | "abandoned" | "interrupted"
    ended_at: str
 
 
class SessionState(BaseModel):
    """Current focus session state."""
    status: str  # "idle" | "running" | "paused" | "completed" | "abandoned"
    active_task: Optional[dict] = None
    duration_minutes: int = 0
    remaining_seconds: int = 0
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    total_paused_seconds: int = 0
 
 
class SessionsResponse(BaseModel):
    """Response for session list endpoint."""
    current: Optional[SessionState] = None
    history: List[SessionHistoryEntry] = []
 
 
# =============================================================================
# In-Memory Session Storage (per user)
# =============================================================================
# Note: In production, you'd use Redis or a database for persistence.
# For now, we'll use in-memory storage with the orchestrator.
 
class SessionManager:
    """Manages focus sessions for a single user."""
    
    def __init__(self):
        self.current_session: Optional[dict] = None
        self.history: List[dict] = []
    
    def start_session(self, task_id: Optional[str], duration_minutes: int) -> dict:
        """Start a new focus session."""
        now = datetime.datetime.now().astimezone()
        
        self.current_session = {
            "id": f"session-{int(now.timestamp())}",
            "task_id": task_id,
            "duration_minutes": duration_minutes,
            "remaining_seconds": duration_minutes * 60,
            "status": "running",
            "started_at": now.isoformat(),
            "paused_at": None,
            "total_paused_seconds": 0,
        }
        
        return self.current_session
    
    def pause_session(self, reason: Optional[str] = None) -> dict:
        """Pause the current session."""
        if not self.current_session or self.current_session["status"] != "running":
            raise ValueError("No running session to pause")
        
        now = datetime.datetime.now().astimezone()
        self.current_session["status"] = "paused"
        self.current_session["paused_at"] = now.isoformat()
        if reason:
            self.current_session["pause_reason"] = reason
        
        return self.current_session
    
    def resume_session(self) -> dict:
        """Resume a paused session."""
        if not self.current_session or self.current_session["status"] != "paused":
            raise ValueError("No paused session to resume")
        
        now = datetime.datetime.now().astimezone()
        paused_at = datetime.datetime.fromisoformat(self.current_session["paused_at"])
        paused_duration = (now - paused_at).total_seconds()
        
        self.current_session["status"] = "running"
        self.current_session["total_paused_seconds"] += int(paused_duration)
        self.current_session["paused_at"] = None
        
        return self.current_session
    
    def abandon_session(self, reason: Optional[str] = None) -> dict:
        """Abandon the current session and add to history."""
        if not self.current_session:
            raise ValueError("No session to abandon")
        
        now = datetime.datetime.now().astimezone()
        started_at = datetime.datetime.fromisoformat(self.current_session["started_at"])
        actual_minutes = (now - started_at).total_seconds() / 60 - (
            self.current_session["total_paused_seconds"] / 60
        )
        
        session_id = self.current_session["id"]
        history_entry = {
            "id": session_id,
            "task_id": self.current_session["task_id"],
            "task_title": None,  # Will be filled by caller if needed
            "duration_minutes": self.current_session["duration_minutes"],
            "actual_minutes": max(0, round(actual_minutes, 2)),
            "outcome": "abandoned",
            "date": self.current_session["started_at"],
            "ended_at": now.isoformat(),
        }
        
        if reason:
            history_entry["reason"] = reason
        
        self.history.insert(0, history_entry)
        self.current_session = None
        
        return history_entry
    
    def complete_session(self, task_title: Optional[str] = None) -> dict:
        """Complete the current session and add to history."""
        if not self.current_session:
            raise ValueError("No session to complete")
        
        now = datetime.datetime.now().astimezone()
        started_at = datetime.datetime.fromisoformat(self.current_session["started_at"])
        actual_minutes = (now - started_at).total_seconds() / 60 - (
            self.current_session["total_paused_seconds"] / 60
        )
        
        session_id = self.current_session["id"]
        history_entry = {
            "id": session_id,
            "task_id": self.current_session["task_id"],
            "task_title": task_title,
            "duration_minutes": self.current_session["duration_minutes"],
            "actual_minutes": max(0, round(actual_minutes, 2)),
            "outcome": "completed",
            "date": self.current_session["started_at"],
            "ended_at": now.isoformat(),
        }
        
        self.history.insert(0, history_entry)
        self.current_session = None
        
        return history_entry
    
    def interrupt_session(self, reason: Optional[str] = None) -> dict:
        """Interrupt the current session (e.g., by distraction detection)."""
        if not self.current_session:
            raise ValueError("No session to interrupt")
        
        now = datetime.datetime.now().astimezone()
        started_at = datetime.datetime.fromisoformat(self.current_session["started_at"])
        actual_minutes = (now - started_at).total_seconds() / 60 - (
            self.current_session["total_paused_seconds"] / 60
        )
        
        session_id = self.current_session["id"]
        history_entry = {
            "id": session_id,
            "task_id": self.current_session["task_id"],
            "task_title": None,
            "duration_minutes": self.current_session["duration_minutes"],
            "actual_minutes": max(0, round(actual_minutes, 2)),
            "outcome": "interrupted",
            "date": self.current_session["started_at"],
            "ended_at": now.isoformat(),
        }
        
        if reason:
            history_entry["reason"] = reason
        
        self.history.insert(0, history_entry)
        self.current_session = None
        
        return history_entry
    
    def get_current_state(self) -> Optional[dict]:
        """Get the current session state."""
        return self.current_session
    
    def get_history(self) -> List[dict]:
        """Get session history."""
        return self.history
 
 
# Global session managers per user (using app state)
_session_managers = {}
 
 
def get_session_manager(user_id: str) -> SessionManager:
    """Get or create a session manager for the user."""
    if user_id not in _session_managers:
        _session_managers[user_id] = SessionManager()
    return _session_managers[user_id]
 
 
def _get_task_title(orchestrator, task_id: Optional[str]) -> Optional[str]:
    """Helper to get task title from orchestrator."""
    if not task_id:
        return None
    
    try:
        plan_manager = orchestrator.plan_manager
        today = datetime.date.today()
        tasks, _, err = plan_manager._load_tasks(today.isoformat(), False)
        if err or not tasks:
            return None
        
        for task in tasks:
            if task.get("id") == task_id:
                return task.get("title")
    except Exception:
        pass
    
    return None
 
 
# =============================================================================
# API Endpoints
# =============================================================================
 
@router.get("/api/sessions")
async def get_sessions(
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Get current session state and history."""
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")
    
    manager = get_session_manager(user_id)
    
    # Build current session state
    current = None
    if manager.current_session:
        session = manager.current_session
        task_title = None
        if session.get("task_id"):
            task_title = _get_task_title(orchestrator, session["task_id"])
        
        current = {
            "status": session["status"],
            "active_task": {
                "id": session.get("task_id"),
                "title": task_title,
                "duration_minutes": session["duration_minutes"],
                "remaining_seconds": session["remaining_seconds"],
            } if session.get("task_id") or session.get("status") != "idle" else None,
            "duration_minutes": session["duration_minutes"],
            "remaining_seconds": session["remaining_seconds"],
            "started_at": session.get("started_at"),
            "paused_at": session.get("paused_at"),
        }
    
    return {
        "current": current,
        "history": manager.get_history(),
    }
 
 
@router.post("/api/sessions/start")
async def start_session(
    request: SessionStartRequest,
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Start a new focus session."""
    try:
        orchestrator = state.get_orchestrator(user_id)
    except ValueError:
        return error_response(401, "INVALID_USER", "Invalid user id")
    
    if request.duration_minutes <= 0:
        return error_response(400, "INVALID_DURATION", "Duration must be positive")
    
    manager = get_session_manager(user_id)
    
    # If there's a running session, abandon it first
    if manager.current_session and manager.current_session["status"] == "running":
        manager.abandon_session("Starting new session")
    
    session = manager.start_session(request.task_id, request.duration_minutes)
    
    # Notify via SSE
    enqueue_event(
        state.get_event_queue(user_id),
        state.event_loop,
        {
            "event": "session_started",
            "data": {
                "session_id": session["id"],
                "task_id": session["task_id"],
                "duration_minutes": session["duration_minutes"],
            },
        },
    )
    
    return {
        "success": True,
        "session": session,
    }
 
 
@router.post("/api/sessions/pause")
async def pause_session(
    request: SessionPauseRequest,
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Pause the current focus session."""
    manager = get_session_manager(user_id)
    
    try:
        session = manager.pause_session(request.reason)
    except ValueError as e:
        return error_response(400, "NO_RUNNING_SESSION", str(e))
    
    # Notify via SSE
    enqueue_event(
        state.get_event_queue(user_id),
        state.event_loop,
        {
            "event": "session_paused",
            "data": {
                "session_id": session["id"],
                "reason": request.reason,
            },
        },
    )
    
    return {
        "success": True,
        "session": session,
    }
 
 
@router.post("/api/sessions/resume")
async def resume_session(
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Resume a paused focus session."""
    manager = get_session_manager(user_id)
    
    try:
        session = manager.resume_session()
    except ValueError as e:
        return error_response(400, "NO_PAUSED_SESSION", str(e))
    
    # Notify via SSE
    enqueue_event(
        state.get_event_queue(user_id),
        state.event_loop,
        {
            "event": "session_resumed",
            "data": {
                "session_id": session["id"],
            },
        },
    )
    
    return {
        "success": True,
        "session": session,
    }
 
 
@router.post("/api/sessions/abandon")
async def abandon_session(
    request: SessionAbandonRequest,
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Abandon the current focus session."""
    manager = get_session_manager(user_id)
    
    try:
        history_entry = manager.abandon_session(request.reason)
    except ValueError as e:
        return error_response(400, "NO_SESSION", str(e))
    
    # Notify via SSE
    enqueue_event(
        state.get_event_queue(user_id),
        state.event_loop,
        {
            "event": "session_abandoned",
            "data": {
                "session_id": history_entry["id"],
                "reason": request.reason,
            },
        },
    )
    
    return {
        "success": True,
        "history_entry": history_entry,
    }
 
 
@router.post("/api/sessions/complete")
async def complete_session(
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Mark the current session as completed (called when timer reaches 0)."""
    manager = get_session_manager(user_id)
    
    try:
        orchestrator = state.get_orchestrator(user_id)
        task_title = None
        if manager.current_session:
            task_title = _get_task_title(
                orchestrator,
                manager.current_session.get("task_id")
            )
        history_entry = manager.complete_session(task_title)
    except ValueError as e:
        return error_response(400, "NO_SESSION", str(e))
    
    # Notify via SSE
    enqueue_event(
        state.get_event_queue(user_id),
        state.event_loop,
        {
            "event": "session_completed",
            "data": {
                "session_id": history_entry["id"],
                "task_title": history_entry["task_title"],
                "duration_minutes": history_entry["duration_minutes"],
            },
        },
    )
    
    return {
        "success": True,
        "history_entry": history_entry,
    }
 
 
@router.get("/api/sessions/history")
async def get_session_history(
    limit: int = 10,
    state=Depends(get_app_state),
    user_id=Depends(get_user_id),
):
    """Get session history."""
    manager = get_session_manager(user_id)
    history = manager.get_history()
    
    return {
        "history": history[:limit],
        "total": len(history),
    }