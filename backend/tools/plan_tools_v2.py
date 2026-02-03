import datetime
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union


# Debug logger: write straight to file to avoid console noise.
def debug_log(message):
    try:
        # Get backend dir (this file lives under backend/tools)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(base_dir, "FORCE_DEBUG.txt")

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # never raise


# Module load marker
debug_log(">>> plan_tools_v2 module loaded <<<")


class PlanManager:
    """
    Manage daily_tasks_YYYY-MM-DD.json read/write and conflict detection.
    Goal: provide PlannerAgent with reliable context and tymebox adjustments.
    """

    def __init__(self, plan_dir: Optional[str] = None, calendar=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_plan_dir = os.path.join(base_dir, "adhd_brain")
        self.plan_dir = plan_dir or default_plan_dir
        os.makedirs(self.plan_dir, exist_ok=True)
        self.calendar = calendar

    # -- Public methods --

    def get_current_context(self, target_date: Optional[str] = None) -> str:
        """
        Return current date/time/timezone and today's plan summary (if any).
        Ensures the agent does not schedule into the past.
        """
        now = datetime.datetime.now().astimezone()
        now_text = now.strftime("%Y-%m-%d %H:%M %Z (UTC%z)")
        today = now.date()
        plan_date, date_err = self._parse_plan_date(target_date, today)
        header = f"Current time: {now_text}"
        if plan_date != today:
            header = f"{header}\nFocus date: {plan_date.isoformat()}"
        if date_err:
            return f"{header}\nDate parse error: {date_err}"

        tasks, path, err = self._load_tasks(
            plan_date.isoformat(), create_if_missing=False
        )
        if err:
            return f"{header}\nPlan read failed: {err}"
        if tasks is None or not tasks:
            return (
                f"{header}\nNo plan file yet: {self._plan_path(plan_date.isoformat())}"
            )

        summary_lines = []
        plan_date = self._plan_date_from_path(path)
        normalized = self._normalize_for_summary(tasks, plan_date)
        for idx, task in enumerate(normalized, start=1):
            start_text = (
                task["start_dt"].strftime("%H:%M")
                if task["start_dt"]
                else (task["raw_start"] or "-")
            )
            end_text = (
                task["end_dt"].strftime("%H:%M")
                if task["end_dt"]
                else (task["raw_end"] or "-")
            )
            duration = self._format_duration(task["start_dt"], task["end_dt"])
            duration_mark = f" ({duration} min)" if duration else ""
            title = task.get("title") or f"Task {idx}"
            status = task.get("status", "pending")
            status_mark = f" [{status}]" if status != "pending" else ""
            summary_lines.append(
                f"{idx}. {start_text}-{end_text}{duration_mark} | {title}{status_mark}"
            )
        summary = "\n".join(summary_lines)
        return f"{header}\nPlan:\n{summary}"

    def create_daily_plan(
        self, tasks: Union[List[Dict], str], target_date: Optional[str] = None
    ) -> str:
        """
        [Smart merge] Update or create the plan for a date (default today).
        If a plan exists, merge new tasks (upsert) instead of overwriting.
        Prevents losing old tasks when only new ones are sent.
        """
        # Entry marker
        debug_log(f"create_daily_plan (Smart Merge) called. Param type: {type(tasks)}")
        debug_log(f"Raw data preview: {str(tasks)[:100]}...")

        # --- 1. Parse and validate params ---
        original_tasks = tasks
        if isinstance(tasks, str):
            try:
                tasks = json.loads(tasks)
            except json.JSONDecodeError as exc:
                err_msg = f"JSON parse error: {exc}"
                debug_log(err_msg)
                return f"❌ Plan creation failed: tasks JSON parse error: {exc}"

        if not isinstance(tasks, list):
            err_msg = f"Type error: expected list, got {type(original_tasks).__name__}"
            debug_log(err_msg)
            return "❌ Plan creation failed: tasks must be a list."

        now = datetime.datetime.now().astimezone()
        plan_date, date_err = self._determine_plan_date(
            target_date=target_date, tasks=tasks, today=now.date()
        )
        if date_err:
            return f"❌ Plan creation failed: {date_err}"

        # --- 2. Normalize new tasks ---
        normalized_new_tasks = []
        errors = []

        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue

            title = (task.get("title") or "").strip()
            if not title:
                continue  # skip untitled tasks

            # Parse times
            start_dt = self._normalize_to_dt(task.get("start"), plan_date)
            end_dt = self._normalize_to_dt(task.get("end"), plan_date)

            # Basic validation
            if not start_dt or not end_dt:
                errors.append(f"Task '{title}' has invalid time format")
                continue

            # Date consistency check
            if start_dt.date() != plan_date or end_dt.date() != plan_date:
                errors.append(
                    f"Task '{title}' date {start_dt.date()} does not match target date {plan_date}"
                )
                continue

            normalized_task = {**task}
            # Ensure ID exists; if not, use title or timestamp
            if not normalized_task.get("id"):
                normalized_task["id"] = f"task_{int(now.timestamp())}_{idx}"

            normalized_task["title"] = title
            normalized_task["start"] = start_dt.strftime("%Y-%m-%d %H:%M")
            normalized_task["end"] = end_dt.strftime("%Y-%m-%d %H:%M")
            normalized_task.setdefault("type", "work")
            # Default to pending unless provided
            normalized_task.setdefault("status", "pending")

            normalized_new_tasks.append(normalized_task)

        if not normalized_new_tasks and errors:
            debug_log(f"Task validation failed: {errors}")
            return "❌ Unable to add tasks: " + "; ".join(errors)

        # --- 3. Smart merge: load existing tasks and merge ---
        plan_date_str = plan_date.isoformat()
        existing_tasks, path, _ = self._load_tasks(
            plan_date_str, create_if_missing=True
        )
        if existing_tasks is None:
            existing_tasks = []

        # Merge using title or id as the key; update existing with new.
        task_map = {}
        for t in existing_tasks:
            key = t.get("id") or t.get("title")
            task_map[key] = t

        added_count = 0
        updated_count = 0
        sync_success = 0
        sync_errors: List[str] = []

        for new_t in normalized_new_tasks:
            key = new_t.get("id") or new_t.get("title")
            if not key:
                continue

            old_task = task_map.get(key)
            merged_task = {**(old_task or {}), **new_t}

            # Preserve old status unless explicitly provided
            if old_task and "status" not in new_t:
                merged_task["status"] = old_task.get("status", "pending")
            merged_task.setdefault("status", "pending")

            # Preserve calendar event id
            merged_task["google_event_id"] = merged_task.get("google_event_id") or (
                old_task.get("google_event_id") if old_task else None
            )

            action = "update" if old_task else "create"
            # Skip calendar sync if unchanged and already has an event id
            needs_sync = True
            if old_task:
                unchanged = (
                    merged_task.get("google_event_id")
                    and merged_task.get("start") == old_task.get("start")
                    and merged_task.get("end") == old_task.get("end")
                    and merged_task.get("title") == old_task.get("title")
                )
                needs_sync = not unchanged

            if needs_sync:
                synced, event_id, sync_msg = self._sync_calendar(merged_task, action)
                merged_task["google_event_id"] = event_id or merged_task.get(
                    "google_event_id"
                )
                if synced:
                    sync_success += 1
                elif sync_msg:
                    sync_errors.append(
                        f"{merged_task.get('title')}: {sync_msg.lstrip(',')}"
                    )

            task_map[key] = merged_task
            if old_task:
                updated_count += 1
            else:
                added_count += 1

        final_tasks = list(task_map.values())
        final_tasks.sort(key=lambda t: t.get("start", ""))

        # --- 4. Write file ---
        debug_log(f"Writing file: {path}, tasks: {len(final_tasks)}")
        write_err = self._write_tasks(path, final_tasks)
        if write_err:
            debug_log(f"❌ Fatal: write failed - {write_err}")
            return f"❌ Write failed: {write_err}"

        # --- 5. Calendar sync feedback ---
        sync_msg = ""
        if sync_success:
            sync_msg = f" (synced {sync_success} to calendar)"
        if sync_errors:
            sync_msg = f"{sync_msg} (failed {len(sync_errors)} syncs; see logs)"

        action_msg = []
        if added_count:
            action_msg.append(f"added {added_count}")
        if updated_count:
            action_msg.append(f"updated {updated_count}")

        result_msg = (
            f"✅ Plan updated (date: {plan_date_str}). "
            f"{', '.join(action_msg)}. Total tasks: {len(final_tasks)}.{sync_msg}"
        )
        return result_msg

    def update_schedule(
        self,
        task_id: str,
        new_start: str,
        new_end: str,
        new_title: Optional[str] = None,
        force: bool = False,
        target_date: Optional[str] = None,
    ) -> str:
        """
        Modify an existing task or insert a new one.
        - On conflict, return CONFLICT (unless force=True).
        - On success, write JSON and attempt calendar sync.
        - target_date selects which day (default today).
        - Numeric task_id is treated as a 1-based index.
        """
        today = datetime.date.today()
        plan_date, date_err = self._determine_plan_date_for_update(
            new_start=new_start, new_end=new_end, target_date=target_date, today=today
        )
        if date_err:
            return f"❌ Update failed: {date_err}"

        plan_date_str = plan_date.isoformat()
        tasks, path, err = self._load_tasks(plan_date_str, create_if_missing=True)
        if err:
            return f"❌ Update failed: {err}"
        if tasks is None:
            return f"❌ Update failed: invalid plan format: {path}"

        plan_date = self._plan_date_from_path(path)
        start_dt = self._normalize_to_dt(new_start, plan_date)
        end_dt = self._normalize_to_dt(new_end, plan_date)
        if not start_dt or not end_dt:
            return f"❌ Unable to parse time: {new_start} -> {new_end}"
        if start_dt.date() != plan_date or end_dt.date() != plan_date:
            return f"❌ Only supports {plan_date.isoformat()} tasks; date mismatch."
        if end_dt <= start_dt:
            return "❌ End time must be after start time."
        if start_dt < datetime.datetime.now().astimezone():
            return f"❌ New start time {start_dt.strftime('%H:%M')} is earlier than now."

        target_task = self._find_task(tasks, task_id)
        conflicts = self._find_conflicts(
            tasks, start_dt, end_dt, plan_date, exclude=target_task
        )

        if conflicts and not force:
            conflict_names = ", ".join(
                [c.get("title") or c.get("id") or "Untitled task" for c in conflicts]
            )
            return f"CONFLICT: {conflict_names}"

        if conflicts:
            for c in conflicts:
            # Delete old calendar events to avoid duplicates
                self._sync_calendar(c, "delete")
                tasks.remove(c)

        start_text = start_dt.strftime("%Y-%m-%d %H:%M")
        end_text = end_dt.strftime("%Y-%m-%d %H:%M")
        created = False

        if target_task:
            target_task["start"] = start_text
            target_task["end"] = end_text
            if new_title:
                target_task["title"] = new_title
        else:
            # No task found and no new_title -> reject creation
            if not new_title:
                return (
                    f"❌ Task with ID '{task_id}' not found. "
                    "To create a new task, provide new_title."
                )

            new_task = {
                "id": task_id,
                "title": new_title,
                "start": start_text,
                "end": end_text,
                "type": "work",
                "status": "pending",  # default status
                "google_event_id": None,
            }
            tasks.append(new_task)
            target_task = new_task
            created = True

        tasks.sort(key=lambda t: t.get("start", ""))

        action_for_calendar = (
            "create" if created or not target_task.get("google_event_id") else "update"
        )
        _, event_id, sync_msg = self._sync_calendar(target_task, action_for_calendar)
        if event_id:
            target_task["google_event_id"] = event_id

        write_err = self._write_tasks(path, tasks)
        if write_err:
            return f"❌ Write failed: {write_err}"

        action = "added" if created else "updated"
        replaced = f", replaced {len(conflicts)} conflicting tasks" if conflicts else ""
        return (
            f"✅ {action} {task_id}: {start_text[11:]}-{end_text[11:]}{replaced}{sync_msg}"
        )

    def list_tasks(self, target_date: Optional[str] = None) -> str:
        """List tasks for a given date (default today)."""
        today = datetime.date.today()
        plan_date, date_err = self._parse_plan_date(target_date, today)
        if date_err:
            return f"❌ {date_err}"

        plan_date_str = plan_date.isoformat()
        tasks, path, err = self._load_tasks(plan_date_str, create_if_missing=False)
        if err:
            return f"❌ {err}"
        if tasks is None or not tasks:
            prefix = "No plan for today" if plan_date == today else "No plan"
            return f"{prefix}: {self._plan_path(plan_date_str)}"

        plan_date = self._plan_date_from_path(path)
        normalized = self._normalize_for_summary(tasks, plan_date)
        lines = [f"Plan file: {path}"]
        for idx, task in enumerate(normalized, start=1):
            start_text = (
                task["start_dt"].strftime("%H:%M")
                if task["start_dt"]
                else (task["raw_start"] or "-")
            )
            end_text = (
                task["end_dt"].strftime("%H:%M")
                if task["end_dt"]
                else (task["raw_end"] or "-")
            )
            duration = self._format_duration(task["start_dt"], task["end_dt"])
            duration_mark = f" ({duration} min)" if duration else ""
            title = task.get("title") or f"Task {idx}"
            status = task.get("status", "pending")
            lines.append(
                f"{idx}. {start_text}-{end_text}{duration_mark} | {title} [{status}]"
            )
        return "\n".join(lines)

    # -- Internal helpers --

    def _plan_path(self, date_str: str) -> str:
        return os.path.join(self.plan_dir, f"daily_tasks_{date_str}.json")

    def _plan_date_from_path(self, path: str) -> datetime.date:
        try:
            return datetime.datetime.strptime(
                os.path.basename(path).replace("daily_tasks_", "").replace(".json", ""),
                "%Y-%m-%d",
            ).date()
        except Exception:
            return datetime.date.today()

    def _load_tasks(
        self, target_date: str, create_if_missing: bool
    ) -> Tuple[Optional[List[Dict]], str, Optional[str]]:
        path = self._plan_path(target_date)
        if not os.path.exists(path):
            if create_if_missing:
                return [], path, None
            return None, path, f"Plan file not found: {path}"
        try:
            with open(path, "r") as f:
                tasks = json.load(f)
        except Exception as exc:
            return None, path, f"Plan read failed: {exc}"
        if not isinstance(tasks, list):
            return None, path, "Plan file format should be a list."
        return tasks, path, None

    def _write_tasks(self, path: str, tasks: List[Dict]) -> Optional[str]:
        """Persist tasks list to disk, returning error text on failure."""
        try:
            with open(path, "w") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            return None
        except Exception as exc:
            return str(exc)

    def _normalize_to_dt(
        self, raw_value: Optional[str], plan_date: datetime.date
    ) -> Optional[datetime.datetime]:
        """Parse common formats into tz-aware datetime."""
        if not raw_value or not isinstance(raw_value, str):
            return None
        value = raw_value.strip()
        tzinfo = datetime.datetime.now().astimezone().tzinfo

        try:
            dt = datetime.datetime.fromisoformat(value.replace("T", " "))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tzinfo)
            return dt.astimezone(tzinfo)
        except Exception:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.datetime.strptime(value, fmt)
                return dt.replace(tzinfo=tzinfo)
            except ValueError:
                continue

        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.datetime.strptime(value, fmt).time()
                return datetime.datetime.combine(plan_date, t).replace(tzinfo=tzinfo)
            except ValueError:
                continue

        return None

    def _find_task(self, tasks: List[Dict], task_id: str) -> Optional[Dict]:
        """Find task by id, title, or index (1-based string)."""
        # 1) Exact ID or title match
        for task in tasks:
            if task.get("id") == task_id or task.get("title") == task_id:
                return task

        # 2) Try 1-based index
        if task_id.isdigit():
            try:
                idx = int(task_id) - 1
                # Sort by time so indexes match list_tasks ordering
                sorted_tasks = sorted(tasks, key=lambda t: t.get("start") or "")
                if 0 <= idx < len(sorted_tasks):
                    return sorted_tasks[idx]
            except (ValueError, IndexError):
                pass

        return None

    def _find_conflicts(
        self,
        tasks: List[Dict],
        start_dt: datetime.datetime,
        end_dt: datetime.datetime,
        plan_date: datetime.date,
        exclude: Optional[Dict] = None,
    ) -> List[Dict]:
        conflicts: List[Dict] = []
        for task in tasks:
            if task is exclude:
                continue
            t_start = self._normalize_to_dt(task.get("start"), plan_date)
            t_end = self._normalize_to_dt(task.get("end"), plan_date)
            if not t_start or not t_end:
                continue
            if start_dt < t_end and end_dt > t_start:
                conflicts.append(task)
        return conflicts

    def _normalize_for_summary(
        self, tasks: List[Dict], plan_date: datetime.date
    ) -> List[Dict]:
        """Sort for summary and include parsed times."""
        normalized = []
        for task in tasks:
            start_dt = self._normalize_to_dt(task.get("start"), plan_date)
            end_dt = self._normalize_to_dt(task.get("end"), plan_date)
            normalized.append(
                {
                    **task,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "raw_start": task.get("start"),
                    "raw_end": task.get("end"),
                }
            )
        normalized.sort(
            key=lambda t: t.get("start_dt")
            or datetime.datetime.max.replace(
                tzinfo=datetime.datetime.now().astimezone().tzinfo
            )
        )
        return normalized

    def _parse_plan_date(
        self, target_date: Optional[Union[str, datetime.date]], today: datetime.date
    ) -> Tuple[datetime.date, Optional[str]]:
        """Parse target_date into a date; support today/tomorrow keywords."""
        if target_date is None:
            return today, None
        if isinstance(target_date, datetime.date):
            return target_date, None

        text = str(target_date).strip().lower()
        if text in {"today", "今天"}:
            return today, None
        if text in {"tomorrow", "明天"}:
            return today + datetime.timedelta(days=1), None
        if text in {"yesterday", "昨天"}:
            return today - datetime.timedelta(days=1), None

        try:
            parsed = datetime.datetime.strptime(text, "%Y-%m-%d").date()
            return parsed, None
        except Exception:
            return (
                today,
                f"Unable to parse target date: {target_date} (expected YYYY-MM-DD or tomorrow).",
            )

    def _extract_date_from_text(self, value: Optional[str]) -> Optional[datetime.date]:
        """Extract date component from a datetime string if present."""
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        try:
            dt = datetime.datetime.fromisoformat(text.replace("T", " "))
            return dt.date()
        except Exception:
            pass
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            try:
                return datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def _determine_plan_date(
        self,
        target_date: Optional[str],
        tasks: List[Dict],
        today: datetime.date,
    ) -> Tuple[datetime.date, Optional[str]]:
        """Decide which date's plan file to touch based on target_date or task dates."""
        plan_date, date_err = self._parse_plan_date(target_date, today)
        if date_err:
            return plan_date, date_err

        explicit_dates = []
        for task in tasks:
            for key in ("start", "end"):
                detected = self._extract_date_from_text(task.get(key))
                if detected and detected not in explicit_dates:
                    explicit_dates.append(detected)

        if explicit_dates:
            if not target_date:
                plan_date = explicit_dates[0]
            if any(d != plan_date for d in explicit_dates):
                dates_text = ", ".join(sorted({d.isoformat() for d in explicit_dates}))
                return (
                    plan_date,
                    f"Tasks span multiple dates: {dates_text}. Split them or set a single target_date.",
                )

        return plan_date, None

    def _determine_plan_date_for_update(
        self,
        new_start: str,
        new_end: str,
        target_date: Optional[str],
        today: datetime.date,
    ) -> Tuple[datetime.date, Optional[str]]:
        """Resolve plan date for update/insert operations."""
        plan_date, date_err = self._parse_plan_date(target_date, today)
        if date_err:
            return plan_date, date_err

        explicit_dates = [
            d
            for d in (
                self._extract_date_from_text(new_start),
                self._extract_date_from_text(new_end),
            )
            if d
        ]
        if explicit_dates:
            base = explicit_dates[0]
            if not target_date:
                plan_date = base
            if any(d != plan_date for d in explicit_dates):
                return plan_date, "Start/end times are not on the same day; adjust or set target_date."
            if target_date and plan_date != base:
                return (
                    plan_date,
                    f"target_date={plan_date.isoformat()} does not match time date {base.isoformat()}",
                )

        return plan_date, None

    def _format_duration(
        self,
        start_dt: Optional[datetime.datetime],
        end_dt: Optional[datetime.datetime],
    ) -> Optional[int]:
        """Calculate duration in minutes if both times are valid and positive."""
        if not start_dt or not end_dt:
            return None
        try:
            minutes = int((end_dt - start_dt).total_seconds() // 60)
            return minutes if minutes > 0 else None
        except Exception:
            return None

    def _format_calendar_time(self, value: Optional[str]) -> Optional[str]:
        """Normalize stored 'YYYY-MM-DD HH:MM' to ISO-like 'YYYY-MM-DDTHH:MM:SS'."""
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        if "T" not in text and " " in text:
            text = text.replace(" ", "T")
        if "T" not in text:
            return text
        # Ensure seconds are present to satisfy GoogleCalendar parser
        if len(text.split("T", 1)[1]) == 5:
            text = f"{text}:00"
        return text

    def _extract_event_id(self, response: Union[str, Dict]) -> Optional[str]:
        """Best-effort extraction of event id from ConnectOnion GoogleCalendar responses."""
        if isinstance(response, dict):
            if "id" in response:
                return str(response.get("id"))
            if "event_id" in response:
                return str(response.get("event_id"))
        if not response:
            return None
        text = str(response)
        match = re.search(r"Event ID:\s*([^\s]+)", text)
        if match:
            return match.group(1).strip()
        match = re.search(r"Event deleted:\s*([^\s]+)", text)
        if match:
            return match.group(1).strip()
        return None

    def _sync_calendar(
        self, task: Dict, action: str
    ) -> Tuple[bool, Optional[str], str]:
        """
        Try syncing to Google Calendar; never raise on failure.
        Returns (success, event_id, message); action: create/update/delete.
        """
        title = task.get("title") or task.get("id") or "Untitled task"
        event_id = task.get("google_event_id")
        start = task.get("start")
        end = task.get("end")

        # 1) Defensive validation
        if not self.calendar or isinstance(self.calendar, str):
            debug_log(f"[Calendar] Not configured or invalid type: {type(self.calendar)}")
            return False, event_id, ""
        if hasattr(self.calendar, "reason"):
            debug_log(f"[Calendar] Fallback mode: {self.calendar.reason}")
            return False, event_id, ""

        iso_start = self._format_calendar_time(start)
        iso_end = self._format_calendar_time(end)
        if action in {"create", "update"} and (not iso_start or not iso_end):
            debug_log(
                f"[Calendar] Invalid time format; skip sync: {title} | {start}-{end} ({action})"
            )
            return False, event_id, ""

        # 2. Delete old event (for conflict cleanup)
        if action == "delete":
            if not event_id:
                debug_log(f"[Calendar] Skip delete: no event_id for {title}")
                return False, None, ""
            if not hasattr(self.calendar, "delete_event"):
                debug_log("[Calendar] Calendar lacks delete_event method")
                return False, event_id, ""
            try:
                try:
                    resp = self.calendar.delete_event(event_id=event_id)
                except TypeError:
                    resp = self.calendar.delete_event(event_id)
                debug_log(f"[Calendar] ✅ Delete ok {event_id} | response: {resp}")
                return True, None, ""
            except Exception as exc:
                debug_log(f"[Calendar] ❌ Delete failed {event_id}: {exc}")
                return False, event_id, f", but calendar sync failed: {exc}"

        # 3) Create event
        def _create_event() -> Tuple[bool, Optional[str], str]:
            if not hasattr(self.calendar, "create_event"):
                debug_log("[Calendar] Calendar lacks create_event method")
                return False, event_id, ""
            try:
                try:
                    resp = self.calendar.create_event(
                        title=title, start_time=iso_start, end_time=iso_end
                    )
                except TypeError:
                    resp = self.calendar.create_event(
                        title=title, start=iso_start, end=iso_end
                    )
                new_id = self._extract_event_id(resp) or event_id
                debug_log(
                    f"[Calendar] ✅ Create ok {title} | id={new_id} | response: {resp}"
                )
                return True, new_id, " and synced to calendar"
            except Exception as exc:
                debug_log(
                    f"[Calendar] ❌ Create failed {title} {iso_start}-{iso_end}: {exc}"
                )
                return False, event_id, f", but calendar sync failed: {exc}"

        # 4) Update event; fallback to create on failure
        if action == "update" and event_id and hasattr(self.calendar, "update_event"):
            try:
                try:
                    resp = self.calendar.update_event(
                        event_id=event_id,
                        title=title,
                        start_time=iso_start,
                        end_time=iso_end,
                    )
                except TypeError:
                    resp = self.calendar.update_event(
                        event_id,
                        title=title,
                        start=iso_start,
                        end=iso_end,
                    )
                new_id = self._extract_event_id(resp) or event_id
                debug_log(
                    f"[Calendar] ✅ Update ok {title} | id={new_id} | response: {resp}"
                )
                return True, new_id, " and synced to calendar"
            except Exception as exc:
                debug_log(
                    f"[Calendar] Update failed, retry create {title} ({event_id}): {exc}"
                )
                return _create_event()

        # Default to create
        return _create_event()
