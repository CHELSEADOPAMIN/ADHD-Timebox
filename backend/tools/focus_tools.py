import datetime
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from core.paths import resolve_data_root
from tools.plan_tools_v2 import PlanManager
from tools.reward_tools import RewardToolkit


def _safe_parse_dt(value: Optional[str], plan_date: datetime.date, tzinfo) -> Optional[datetime.datetime]:
    """Parse common datetime/time formats into aware datetime."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(value, fmt).replace(tzinfo=tzinfo)
        except ValueError:
            continue
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.datetime.strptime(value, fmt).time()
            return datetime.datetime.combine(plan_date, t).replace(tzinfo=tzinfo)
        except ValueError:
            continue
    return None


class ContextTool:
    """
    Provides active window and current task state to prevent the LLM from guessing.
    - get_active_window(): returns macOS frontmost app and window title.
    - get_idle_seconds(): returns idle seconds (macOS only, requires ioreg).
    - get_focus_state(): returns time, plan path, current/next task, remaining minutes.
    """

    def __init__(self, plan_dir: Optional[str] = None):
        self.plan_dir = plan_dir or resolve_data_root()
        os.makedirs(self.plan_dir, exist_ok=True)

    # -- Public tool methods --

    def get_active_window(self) -> str:
        """Read the current frontmost window on macOS; return reason on failure."""
        script = (
            'tell application "System Events" to get name of first application process whose frontmost is true\n'
            "set frontApp to result\n"
            "set windowTitle to \"\"\n"
            "try\n"
            "    tell application frontApp to set windowTitle to name of front window\n"
            "end try\n"
            'return frontApp & " - " & windowTitle'
        )
        try:
            output = subprocess.check_output(["osascript", "-e", script], timeout=2)
            text = output.decode("utf-8", errors="ignore").strip()
            return text or "Unable to read window title."
        except FileNotFoundError:
            return "osascript unavailable (likely not macOS)."
        except subprocess.TimeoutExpired:
            return "Front window query timed out."
        except Exception as exc:
            return f"Failed to read active window: {exc}"

    def get_idle_seconds(self) -> Optional[int]:
        """Read system idle time (seconds) via ioreg; macOS only."""
        try:
            output = subprocess.check_output(["ioreg", "-c", "IOHIDSystem"], timeout=2)
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

        text = ""
        try:
            text = output.decode("utf-8", errors="ignore")
        except Exception:
            return None

        match = re.search(r'HIDIdleTime\" = (\d+)', text)
        if not match:
            return None

        try:
            nanoseconds = int(match.group(1))
            return int(nanoseconds / 1_000_000_000)
        except Exception:
            return None

    def get_focus_state(self) -> Dict[str, Any]:
        """
        Return structured focus state.
        Fields:
        - status: current/upcoming/finished/no_plan/empty
        - active_task: {title,start,end,remaining_minutes,plan_date}
        - progress: {done,total}
        - plan_path: plan file path
        - now: ISO timestamp
        - message: friendly summary
        """
        now = datetime.datetime.now().astimezone()
        plan_path = self._resolve_plan_path()
        if not plan_path:
            return {
                "status": "no_plan",
                "active_task": None,
                "progress": {"done": 0, "total": 0},
                "plan_path": None,
                "now": now.isoformat(),
                "message": f"Plan file not found. Directory: {self.plan_dir}",
            }

        tasks, plan_date = self._load_tasks(plan_path)
        if tasks is None:
            return {
                "status": "empty",
                "active_task": None,
                "progress": {"done": 0, "total": 0},
                "plan_path": plan_path,
                "now": now.isoformat(),
                "message": f"Plan file is empty: {plan_path}",
            }

        normalized = self._normalize_tasks(tasks, plan_date)
        status, task = self._determine_focus_task(normalized, now)
        active_task = None
        if task:
            include_date = plan_date != datetime.date.today()
            start_text = self._format_time(task.get("start_dt"), include_date)
            end_text = self._format_time(task.get("end_dt"), include_date)
            remaining = None
            if task.get("end_dt"):
                remaining = max(int((task["end_dt"] - now).total_seconds() // 60), 0)
            active_task = {
                "title": task.get("title") or "current task",
                "start": start_text,
                "end": end_text,
                "remaining_minutes": remaining,
                "plan_date": plan_date.isoformat(),
            }
        progress = {
            "done": len([t for t in normalized if t.get("status") == "done"]),
            "total": len(normalized),
        }
        message = self._build_message(status, active_task)
        return {
            "status": status,
            "active_task": active_task,
            "progress": progress,
            "plan_path": plan_path,
            "now": now.isoformat(),
            "message": message,
        }

    # -- Internal helpers --

    def _resolve_plan_path(self) -> Optional[str]:
        today = datetime.date.today().isoformat()
        today_path = os.path.join(self.plan_dir, f"daily_tasks_{today}.json")
        if os.path.exists(today_path):
            return today_path
        candidates = sorted(
            (
                f
                for f in os.listdir(self.plan_dir)
                if f.startswith("daily_tasks_") and f.endswith(".json")
            )
        )
        if not candidates:
            return None
        return os.path.join(self.plan_dir, candidates[-1])

    def _load_tasks(self, path: str) -> Tuple[Optional[List[Dict[str, Any]]], datetime.date]:
        try:
            with open(path, "r") as f:
                tasks = json.load(f)
        except Exception:
            return None, datetime.date.today()
        plan_date = self._plan_date_from_path(path)
        if not isinstance(tasks, list):
            return None, plan_date
        return tasks, plan_date

    def _normalize_tasks(self, tasks: List[dict], plan_date: datetime.date) -> List[dict]:
        tzinfo = datetime.datetime.now().astimezone().tzinfo
        normalized = []
        for task in tasks:
            start_dt = _safe_parse_dt(task.get("start"), plan_date, tzinfo)
            end_dt = _safe_parse_dt(task.get("end"), plan_date, tzinfo)
            normalized.append({**task, "start_dt": start_dt, "end_dt": end_dt})
        normalized.sort(
            key=lambda t: t.get("start_dt")
            or datetime.datetime.max.replace(tzinfo=tzinfo)
        )
        return normalized

    def _determine_focus_task(
        self, tasks: List[dict], now: datetime.datetime
    ) -> Tuple[str, Optional[dict]]:
        if not tasks:
            return "empty", None
        timed = [t for t in tasks if t.get("start_dt")]
        if not timed:
            return "no_timed", tasks[0]
        
        # Filter out completed tasks so they are not treated as current focus.
        # If the current window is done, slide to the next upcoming task.
        pending_timed = [
            t for t in timed 
            if str(t.get("status", "")).lower() not in {"done", "completed", "complete"}
        ]
        
        # If all timed tasks are done, mark the last task as finished.
        if not pending_timed:
            return "finished", timed[-1]

        for task in pending_timed:
            start_dt = task.get("start_dt")
            end_dt = task.get("end_dt") or start_dt
            
            # 1) Within time window -> current
            if start_dt <= now <= end_dt:
                return "current", task
            
            # 2) Time window not reached -> upcoming
            # pending_timed is sorted; the first future task is upcoming
            if start_dt > now:
                # Optimization: if the next task starts within 20 minutes and
                # prior tasks are done, treat it as current so IdleWatcher works.
                diff_minutes = (start_dt - now).total_seconds() / 60
                if diff_minutes <= 20:
                     return "current", task
                return "upcoming", task
        
        # If we get here, all pending tasks are overdue or we are between tasks
        # with all prior tasks completed. Fall back to the first pending task.
        return "upcoming", pending_timed[0]

    def _plan_date_from_path(self, path: str) -> datetime.date:
        try:
            return datetime.datetime.strptime(
                os.path.basename(path), "daily_tasks_%Y-%m-%d.json"
            ).date()
        except ValueError:
            return datetime.date.today()

    def _format_time(self, dt_value: Optional[datetime.datetime], include_date: bool) -> str:
        if not dt_value:
            return "-"
        fmt = "%Y-%m-%d %H:%M" if include_date else "%H:%M"
        return dt_value.strftime(fmt)

    def _build_message(self, status: str, active_task: Optional[dict]) -> str:
        if not active_task:
            return "No active task right now."
        title = active_task.get("title", "")
        start = active_task.get("start", "-")
        end = active_task.get("end", "-")
        if status == "current":
            remaining = active_task.get("remaining_minutes")
            tail = f", about {remaining} minutes left" if remaining is not None else ""
            return f"Current task: {title} ({start}-{end}){tail}"
        if status == "upcoming":
            return f"Next task: {title} ({start}-{end})"
        if status == "finished":
            return f"All timed tasks completed. Last task: {title} ({start}-{end})"
        return f"Current task: {title} ({start}-{end})"


class FocusToolkit:
    """
    Focus Agent helper tools:
    - complete_task(task_id): mark a task as done.
    - suggest_micro_step(task_title): offer 2-3 doable micro-steps.
    - white_noise(action): placeholder for noise on/off (text only).
    """

    def __init__(
        self,
        plan_manager: Optional[PlanManager] = None,
        context_tool: Optional[ContextTool] = None,
        reward_toolkit: Optional[RewardToolkit] = None,
    ):
        self.plan_manager = plan_manager or PlanManager()
        self.context_tool = context_tool or ContextTool(plan_dir=self.plan_manager.plan_dir)
        self.reward_toolkit = reward_toolkit or RewardToolkit(brain_dir=self.plan_manager.plan_dir)

    def complete_task(self, task_id: str) -> str:
        """
        Mark a task as completed. task_id can be the ID or part of the title.
        Returns confirmation text or an error message; does not raise.
        """
        lock = getattr(self.plan_manager, "_file_lock", None)
        if lock:
            lock.__enter__()
        try:
            path = self.context_tool._resolve_plan_path()
            if not path:
                return "❌ Plan file not found; cannot complete task."
            tasks, plan_date = self.context_tool._load_tasks(path)
            if tasks is None:
                return f"❌ Plan file not readable: {path}"

            target = self._locate_task(tasks, task_id)
            if target is None:
                return f"❌ Task not found: {task_id}"

            target["status"] = "done"
            target["completed_at"] = datetime.datetime.now().astimezone().isoformat()
            try:
                with open(path, "w") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                return f"❌ Write failed: {exc}"
        finally:
            if lock:
                lock.__exit__(None, None, None)

        title = target.get("title") or task_id
        start_text = target.get("start") or "-"
        end_text = target.get("end") or "-"
        reward_block = ""
        if self.reward_toolkit:
            try:
                reward_block = "\n\n" + self.reward_toolkit.generate_micro_reward(title)
            except Exception as exc:
                reward_block = f"\n\n[Reward generation failed: {exc}]"
        return (
            f"✅ Completed: {title} ({start_text} - {end_text}){reward_block}\n\n"
            "(SYSTEM NOTE: Please display the ASCII Art reward above verbatim; do not omit it.)"
        )

    def suggest_micro_step(self, task_title: str) -> str:
        """
        When the user is stuck, give 2-3 micro-steps that can be done in 5 minutes.
        Text-only; no external services.
        """
        normalized = (task_title or "current task").strip()
        steps = [
            f"Define the smallest done state for \"{normalized}\" in one sentence.",
            "Open the relevant file/doc and insert a TODO at the exact entry point.",
            "Create the first empty function/section skeleton so it runs or saves.",
        ]
        return " / ".join(steps)

    def white_noise(self, action: str) -> str:
        """
        Placeholder: notify start/stop white noise (text only).
        action: start/stop.
        """
        normalized = (action or "").strip().lower()
        if normalized in {"start", "on", "play"}:
            return "🔊 White noise: recorded as ON (text only)."
        if normalized in {"stop", "off", "pause"}:
            return "🤫 White noise: recorded as OFF."
        return "Please specify action=start/stop."

    # -- Internal helpers --

    def _locate_task(self, tasks: List[dict], task_id: str) -> Optional[dict]:
        if not task_id:
            return None
        lowered = task_id.lower()
        for task in tasks:
            if str(task.get("id", "")).lower() == lowered:
                return task
        for task in tasks:
            title = str(task.get("title", "")).lower()
            if lowered in title:
                return task
        return None
