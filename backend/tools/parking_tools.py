"""Shared parking lot service for focus/orchestration agents."""

import datetime
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.model_config import resolve_model
from core.paths import resolve_data_root

try:
    # Preferred package name (avoids runtime warning in duckduckgo_search)
    from ddgs import DDGS  # type: ignore
except ImportError:
    from duckduckgo_search import DDGS  # type: ignore


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    SEARCH = "search"
    MEMO = "memo"
    TODO = "todo"


class ParkingService:
    """Core parking service that stores thoughts and runs optional background search."""

    def __init__(self, brain_dir: Optional[str] = None):
        self.brain_dir = brain_dir or resolve_data_root()
        self.parking_dir = os.path.join(self.brain_dir, "thought_parking")
        os.makedirs(self.parking_dir, exist_ok=True)

        self._current_file = os.path.join(self.parking_dir, "current_parking.json")
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._session_id: Optional[str] = None
        self._lock = threading.RLock()

    # ── Public API ─────────────────────────────────────────────

    def dispatch_task(
        self,
        content: str,
        task_type: str = TaskType.SEARCH.value,
        source: str = "unknown",
        run_async: bool = True,
    ) -> str:
        """
        Primary entry: stash a thought or query, optionally processed in background.
        """
        normalized_type = (task_type or TaskType.SEARCH.value).lower()
        task_id = str(uuid.uuid4())[:8]
        now = datetime.datetime.now()

        task = {
            "id": task_id,
            "content": content,
            "type": normalized_type,
            "source": source,
            "status": TaskStatus.PENDING.value,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": self._session_id,
            "result": None,
            "error": None,
        }

        self._append_task(task)
        self._log_to_daily(
            f"[{now.strftime('%H:%M:%S')}] 📥 Received: {content} (from {source})"
        )

        if run_async and normalized_type == TaskType.SEARCH.value:
            # Fire-and-forget search so it never blocks focus flow.
            self._executor.submit(self._process_task_background, task_id)

        preview = content[:30]
        suffix = "..." if len(content) > 30 else ""
        return f"📥 Logged: \"{preview}{suffix}\""

    def get_session_summary(self, session_id: Optional[str] = None) -> str:
        """
        Retrieve summary for the current or specified session.
        """
        target_session = session_id or self._session_id

        # If session_id is missing, show the most recent session (current behavior: show all).
        if not target_session:
            return "📭 No parked thoughts during this focus session."

        tasks = self._load_tasks()
        session_tasks = [
            t
            for t in tasks
            if t.get("session_id") == target_session or target_session is None
        ]

        if not session_tasks:
            return "📭 No parked thoughts during this focus session."

        lines = ["📋 **Focus session thought summary:**", ""]
        for task in session_tasks:
            status = task.get("status", TaskStatus.PENDING.value)
            content = task.get("content", "")[:50]
            result = task.get("result")

            if status == TaskStatus.COMPLETED.value and result:
                tail = "..." if len(result) > 200 else ""
                lines.append(f"✅ \"{content}\"")
                lines.append(f"   → {result[:200]}{tail}")
            elif status == TaskStatus.PENDING.value:
                lines.append(f"⏳ \"{content}\" - still processing")
            elif status == TaskStatus.FAILED.value:
                lines.append(f"❌ \"{content}\" - failed")
            else:
                lines.append(f"📝 \"{content}\" - logged")
            lines.append("")

        return "\n".join(lines).rstrip()

    def list_pending_tasks(self) -> str:
        """List all pending tasks for quick inspection."""
        tasks = self._load_tasks()
        pending = [t for t in tasks if t.get("status") == TaskStatus.PENDING.value]

        if not pending:
            return "📭 No pending parked thoughts right now."

        lines = [f"📋 Pending thoughts ({len(pending)}):"]
        for task in pending:
            content = task.get("content", "")[:40]
            lines.append(f"  - {content} [{task.get('type', TaskType.MEMO.value)}]")
        return "\n".join(lines)

    def start_session(self) -> str:
        """Mark the beginning of a focus session."""
        self._session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._session_id

    def end_session(self) -> str:
        """End active session and return a formatted summary."""
        if not self._session_id:
            return "📭 No parked thoughts during this focus session."
        summary = self.get_session_summary()
        self._session_id = None
        return summary

    # ── Internal helpers ──────────────────────────────────────

    def _load_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not os.path.exists(self._current_file):
                return []
            try:
                with open(self._current_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def _save_tasks(self, tasks: List[Dict[str, Any]]):
        with self._lock:
            with open(self._current_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

    def _append_task(self, task: Dict[str, Any]):
        with self._lock:
            tasks = self._load_tasks()
            tasks.append(task)
            self._save_tasks(tasks)

    def _update_task(self, task_id: str, updates: Dict[str, Any]):
        with self._lock:
            tasks = self._load_tasks()
            for task in tasks:
                if task.get("id") == task_id:
                    task.update(updates)
                    break
            self._save_tasks(tasks)

    def _log_to_daily(self, message: str):
        # Logging to a text file is append-only, less critical to lock but good practice.
        # However, Python's file append is atomic on POSIX for small writes.
        # We'll lock to be consistent.
        with self._lock:
            today = datetime.date.today().isoformat()
            log_path = os.path.join(self.parking_dir, f"thought_parking_{today}.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(message + "\n")

    def _format_result_for_log(self, result: Optional[str]) -> List[str]:
        """Normalize a potentially multi-line result into concise log lines."""
        if result is None:
            return ["(no result)"]
        lines: List[str] = []
        for raw in str(result).splitlines():
            line = raw.strip()
            if not line:
                continue
            lines.append(line)
            if len(lines) >= 20:
                break
        return lines or ["(no result)"]

    def _process_task_background(self, task_id: str):
        """Execute background work for search tasks without blocking user flow."""
        self._update_task(task_id, {"status": TaskStatus.PROCESSING.value})

        tasks = self._load_tasks()
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if not task:
            return

        content = task.get("content", "")

        try:
            result = self._perform_search(content)
            self._update_task(
                task_id,
                {
                    "status": TaskStatus.COMPLETED.value,
                    "result": result,
                    "completed_at": datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                },
            )
            self._log_to_daily(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Completed: {content[:30]}"
            )
            for line in self._format_result_for_log(result):
                self._log_to_daily(f"   → {line}")
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._update_task(
                task_id, {"status": TaskStatus.FAILED.value, "error": str(exc)}
            )
            self._log_to_daily(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ❌ Failed: {content[:30]}"
            )
            self._log_to_daily(f"   → Error: {exc}")

    def _internet_search(self, query: str) -> str:
        """Search DuckDuckGo and return a formatted summary."""
        query_text = (query or "").strip()
        if not query_text:
            return "No query provided."

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query_text, max_results=3))
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if "429" in message or "too many requests" in lowered:
                return "Search rate-limited. Please try again later."
            if "timeout" in lowered:
                return "Search service temporarily unavailable."
            return f"Search failed: {message}"

        if not results:
            return "No results found. Try different keywords."

        lines: List[str] = ["🔍 Search results:", ""]
        for idx, item in enumerate(results, start=1):
            title = (item.get("title") or "Untitled").strip()
            url = (
                item.get("href")
                or item.get("url")
                or item.get("link")
                or item.get("source")
                or ""
            )
            snippet = (
                item.get("body") or item.get("snippet") or item.get("description") or ""
            )
            snippet = " ".join(str(snippet).split())
            if len(snippet) > 100:
                snippet = snippet[:100].rstrip() + "..."

            lines.append(f"{idx}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   Source: {url}")
            lines.append("")

        lines.append(f"({len(results)} results; full details in current_parking.json)")
        return "\n".join(lines).rstrip()

    def _fetch_with_webfetch(self, url: str) -> str:
        """Fallback to WebFetch for direct URLs."""
        try:
            from connectonion import Agent, WebFetch
        except ImportError:
            return "[System Error] Unable to import ConnectOnion components."

        system_instruction = (
            "Use WebFetch to retrieve and summarize the webpage content. "
            "Only process the provided URL; do not search or guess other links. "
            "Return a concise summary with key points."
        )

        try:
            web_tool = WebFetch()
            searcher = Agent(
                name="parking_searcher",
                model=resolve_model(),
                tools=[web_tool],
                system_prompt=system_instruction,
                quiet=True,
            )
            prompt = (
                "Fetch and summarize the core information from this webpage. "
                "Provide a bullet-style summary:\n"
                f"{url}\n"
                "Do not perform any additional search."
            )
            result = searcher.input(prompt)
            return str(result)
        except Exception as exc:
            return f"[Failed] Web fetch error: {exc}"

    def _perform_search(self, query: str) -> str:
        """
        Search-first flow: keyword uses DuckDuckGo, URL keeps WebFetch summary.
        """
        query_text = (query or "").strip()
        if query_text.lower().startswith(("http://", "https://")):
            return self._fetch_with_webfetch(query_text)
        return self._internet_search(query_text)


class ParkingToolkit:
    """Agent-facing toolkit wrapper around ParkingService."""

    def __init__(self, service: Optional[ParkingService] = None):
        self.service = service or ParkingService()

    def park_thought(
        self, content: str, thought_type: str = TaskType.SEARCH.value
    ) -> str:
        """
        Stash a thought or query for background processing.
        thought_type: search | memo | todo
        """
        normalized_type = (thought_type or TaskType.SEARCH.value).lower()
        return self.service.dispatch_task(
            content=content,
            task_type=normalized_type,
            source="focus_mode",
            run_async=True,
        )

    def get_parking_summary(self) -> str:
        """Return processed results for the active focus session."""
        return self.service.get_session_summary()
