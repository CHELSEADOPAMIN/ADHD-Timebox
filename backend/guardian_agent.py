# guardian_agent.py
# Guardian Agent built on ConnectOnion with class-based tools and a check-in loop.

import datetime
import json
import os

from core.paths import resolve_data_root
import random
import subprocess
import textwrap
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from connectonion import Agent, Memory, WebFetch

from agents.model_config import resolve_model
try:
    from connectonion import GoogleCalendar
except Exception:
    GoogleCalendar = None  # type: ignore

try:
    import cowsay  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cowsay = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADHD_DIR = resolve_data_root()
os.makedirs(ADHD_DIR, exist_ok=True)

PARKING_DIR = os.path.join(ADHD_DIR, "thought_parking")
os.makedirs(PARKING_DIR, exist_ok=True)

HANDOVER_NOTE_FILE = os.path.join(ADHD_DIR, "handover_note.json")
UPDATED_PLAN_FILE = os.path.join(ADHD_DIR, "updated_tasks.json")

PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)


class CalendarFallback:
    """No-op calendar when GoogleCalendar is not available."""

    def __init__(self, reason: str = "calendar unavailable"):
        self.reason = reason

    def create_event(self, title: str, start_time: str, end_time: str, description: str = None, attendees: str = None,
                     location: str = None) -> str:
        return f"[calendar skipped] {self.reason} | {title} {start_time}-{end_time}"

    def update_event(self, event_id: str, title: str = None, start_time: str = None, end_time: str = None,
                     description: str = None, attendees: str = None, location: str = None) -> str:
        return f"[calendar skipped] {self.reason} | update {event_id}"


def _safe_calendar() -> object:
    if GoogleCalendar is None:
        return CalendarFallback("GoogleCalendar import failed")
    try:
        return GoogleCalendar()
    except Exception as exc:  # pragma: no cover - depends on user auth
        return CalendarFallback(str(exc))


class PlanRepository:
    """Read/write daily plans and provide time helpers."""

    def __init__(self, plan_dir: str):
        self.plan_dir = plan_dir
        self._latest: Optional[Dict] = None

    def resolve_plan_path(self, date: Optional[str] = None) -> Optional[str]:
        target = date or datetime.date.today().isoformat()
        today_path = os.path.join(self.plan_dir, f"daily_tasks_{target}.json")
        if os.path.exists(today_path):
            return today_path
        candidates = sorted(
            f for f in os.listdir(self.plan_dir) if f.startswith("daily_tasks_") and f.endswith(".json")
        )
        if not candidates:
            return None
        return os.path.join(self.plan_dir, candidates[-1])

    def _plan_date_from_path(self, path: str) -> datetime.date:
        try:
            return datetime.datetime.strptime(
                os.path.basename(path), "daily_tasks_%Y-%m-%d.json"
            ).date()
        except ValueError:
            return datetime.date.today()

    def _parse_task_time(self, value: Optional[str], plan_date: datetime.date, tzinfo) -> Optional[datetime.datetime]:
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

    def _should_include_date(self, value: Optional[str], plan_date: datetime.date) -> bool:
        if not value:
            return False
        return "-" in value[:10] or plan_date != datetime.date.today()

    def _dt_to_str(self, dt_value: datetime.datetime, include_date: bool) -> str:
        return dt_value.strftime("%Y-%m-%d %H:%M" if include_date else "%H:%M")

    def _normalize_tasks(self, tasks: List[dict], plan_date: datetime.date) -> List[dict]:
        tzinfo = datetime.datetime.now().astimezone().tzinfo
        normalized = []
        for idx, task in enumerate(tasks):
            start_dt = self._parse_task_time(task.get("start"), plan_date, tzinfo)
            end_dt = self._parse_task_time(task.get("end"), plan_date, tzinfo)
            normalized.append(
                {
                    **task,
                    "index": idx,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                }
            )
        normalized.sort(key=lambda t: t["start_dt"] or datetime.datetime.max.replace(tzinfo=tzinfo))
        return normalized

    def load_plan(self, date: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        path = self.resolve_plan_path(date)
        if not path:
            target_date = date or datetime.date.today().isoformat()
            return None, f"Plan file not found: {os.path.join(self.plan_dir, f'daily_tasks_{target_date}.json')}"
        try:
            with open(path, "r") as f:
                tasks = json.load(f)
        except Exception as exc:
            return None, f"Failed to read plan: {exc}"
        if not isinstance(tasks, list):
            return None, "Invalid plan format (expected list)."
        plan_date = self._plan_date_from_path(path)
        normalized = self._normalize_tasks(tasks, plan_date)
        data = {"path": path, "plan_date": plan_date, "tasks": tasks, "normalized": normalized}
        self._latest = data
        return data, None

    def _find_task(self, plan_data: Dict, task_id: str) -> Optional[dict]:
        for t in plan_data.get("tasks", []):
            if t.get("id") == task_id:
                return t
        return None

    def determine_focus(self, plan_data: Dict) -> Tuple[str, Optional[dict]]:
        normalized = plan_data.get("normalized") or []
        if not normalized:
            return "empty", None
        now = datetime.datetime.now().astimezone()
        timed = [t for t in normalized if t.get("start_dt")]
        if not timed:
            return "no_timed", normalized[0]
        for task in timed:
            start_dt = task["start_dt"]
            end_dt = task.get("end_dt") or start_dt
            if start_dt <= now <= end_dt:
                return "current", task
            if start_dt > now:
                return "upcoming", task
        return "finished", timed[-1]

    def save_plan(self, plan_data: Dict, path: Optional[str] = None) -> str:
        target_path = path or plan_data.get("path")
        if not target_path:
            target_path = os.path.join(self.plan_dir, "daily_tasks_updated.json")
        with open(target_path, "w") as f:
            json.dump(plan_data["tasks"], f, ensure_ascii=False, indent=2)
        plan_data["normalized"] = self._normalize_tasks(plan_data["tasks"], plan_data["plan_date"])
        with open(UPDATED_PLAN_FILE, "w") as f:
            json.dump(plan_data["tasks"], f, ensure_ascii=False, indent=2)
        self._latest = plan_data
        return f"Plan updated: {target_path}"

    def shift_remaining(self, plan_data: Dict, anchor_id: str, delay_minutes: int) -> str:
        normalized = plan_data.get("normalized") or []
        anchor = next((t for t in normalized if t.get("id") == anchor_id), None)
        if not anchor:
            return f"Task not found: {anchor_id}"
        delta = datetime.timedelta(minutes=delay_minutes)
        plan_date = plan_data["plan_date"]
        anchor_end = anchor.get("end_dt") or anchor.get("start_dt") or datetime.datetime.now().astimezone()

        # Update anchor end time
        include_anchor_date = self._should_include_date(anchor.get("end") or anchor.get("start"), plan_date)
        new_anchor_end = anchor_end + delta
        plan_data["tasks"][anchor["index"]]["end"] = self._dt_to_str(new_anchor_end, include_anchor_date)

        for task in normalized:
            if task["id"] == anchor_id:
                continue
            start_dt = task.get("start_dt")
            end_dt = task.get("end_dt") or start_dt
            if not start_dt:
                continue
            if start_dt < anchor_end:
                continue
            include_date = self._should_include_date(task.get("start") or task.get("end"), plan_date)
            new_start = start_dt + delta
            new_end = (end_dt + delta) if end_dt else None
            plan_data["tasks"][task["index"]]["start"] = self._dt_to_str(new_start, include_date)
            if new_end:
                plan_data["tasks"][task["index"]]["end"] = self._dt_to_str(new_end, include_date)
        self.save_plan(plan_data)
        return f"Delayed by {delay_minutes} minutes and rescheduled remaining tasks."

    def day_summary(self, plan_data: Optional[Dict]) -> str:
        if not plan_data:
            return "Today's plan is not loaded."
        tasks = plan_data.get("tasks", [])
        done = len([t for t in tasks if t.get("status") == "done"])
        total = len(tasks)
        normalized = plan_data.get("normalized") or []
        minutes = 0
        for task in normalized:
            start = task.get("start_dt")
            end = task.get("end_dt") or start
            if start and end:
                delta = max(0, (end - start).total_seconds() / 60)
                minutes += delta
        hours = f"{minutes/60:.1f}".rstrip("0").rstrip(".") or "0"
        return f"Completed {done}/{total} tasks today, focused {hours} hours."


class ContextAwarenessTool:
    """Sense current environment and task status."""

    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo

    def get_current_context(self) -> str:
        """Return current time, plan overview and focus task."""
        now = datetime.datetime.now().astimezone()
        plan_data, error = self.plan_repo.load_plan()
        header = now.strftime("Current time: %Y-%m-%d %H:%M:%S %Z (UTC%z)")
        if error or not plan_data:
            return f"{header}\n{error or 'Plan not loaded'}"
        status, task = self.plan_repo.determine_focus(plan_data)
        plan_date = plan_data["plan_date"]
        tasks = plan_data.get("tasks", [])
        lines = [header, f"Plan date: {plan_date}, tasks: {len(tasks)}", f"Status: {status}"]
        if task:
            start = task.get("start") or "-"
            end = task.get("end") or "-"
            title = task.get("title") or "current task"
            lines.append(f"Focus: {title} ({start}-{end})")
        return "\n".join(lines)

    def get_active_window(self) -> str:
        """Return the frontmost macOS window and app name."""
        script = textwrap.dedent(
            """
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set windowTitle to ""
                try
                    set windowTitle to name of front window of application process frontApp
                end try
                return frontApp & "::" & windowTitle
            end tell
            """
        ).strip()
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - platform dependent
            return f"Failed to get active window: {exc}"
        if result.returncode != 0:
            return f"osascript error: {result.stderr.strip()}"
        return result.stdout.strip() or "No active window found."


class ThoughtExpanderTool:
    """Handle thought parking and auto-expand search."""

    def __init__(self, plan_repo: PlanRepository, memory: Memory, webfetch: WebFetch):
        self.plan_repo = plan_repo
        self.memory = memory
        self.webfetch = webfetch

    def _parking_path(self) -> str:
        today = datetime.date.today().isoformat()
        return os.path.join(PARKING_DIR, f"thought_parking_{today}.txt")

    def _seasonal_hint(self) -> str:
        month = datetime.date.today().month
        if month in (12, 1, 2):
            return "winter warmth"
        if month in (6, 7, 8):
            return "summer cool"
        return ""

    def _fetch_search_results(self, query: str) -> List[Tuple[str, str]]:
        import urllib.parse
        from bs4 import BeautifulSoup  # type: ignore

        encoded = urllib.parse.quote_plus(query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        html = self.webfetch.fetch(url)
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for link in soup.select("a.result__a"):
            title = link.get_text(strip=True)
            href = link.get("href")
            if title and href:
                items.append((title, href))
            if len(items) >= 5:
                break
        if not items:
            for link in soup.find_all("a", href=True):
                title = link.get_text(strip=True)
                href = link.get("href")
                if title and href and "http" in href:
                    items.append((title, href))
                if len(items) >= 3:
                    break
        return items

    def expand_thought(self, thought: str) -> str:
        """Capture a stray thought, auto-search, and park the findings."""
        seasonal = self._seasonal_hint()
        query = f"{thought.strip()} {seasonal}".strip()
        try:
            results = self._fetch_search_results(query)
        except Exception as exc:
            results = []
            fetch_error = f"Search failed: {exc}"
        else:
            fetch_error = ""

        lines = [f"Thought: {thought}", f"Query: {query}"]
        if results:
            lines.append("Results:")
            for title, href in results:
                lines.append(f"- {title} | {href}")
        elif fetch_error:
            lines.append(fetch_error)
        else:
            lines.append("No valid results found, but the thought is logged.")

        parking_path = self._parking_path()
        ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        record = f"[{ts}]\n" + "\n".join(lines) + "\n\n"
        with open(parking_path, "a") as f:
            f.write(record)

        memory_key = f"thought_{datetime.date.today().isoformat()}"
        self.memory.write_memory(memory_key, "\n".join(lines))
        return (
            f"Logged to thought parking ({parking_path}). "
            f"{fetch_error or 'Stay on the current task; handle these ideas later.'}"
        )


class ScheduleManagerTool:
    """Manage task progress and flexible rescheduling."""

    def __init__(self, plan_repo: PlanRepository, memory: Memory, calendar: object):
        self.plan_repo = plan_repo
        self.memory = memory
        self.calendar = calendar
        self.micro_tasks = [
            "Write just the first sentence.",
            "Open the document and type the title.",
            "Tidy your desk for 3 minutes.",
            "Write down one question you need to answer.",
            "Read one short reference paragraph.",
            "Set a 5-minute timer, think nothing, and start.",
            "Pour a glass of water and return to your seat.",
        ]

    def check_task_status(self, task_id: str) -> str:
        """Check start/end/status for a task."""
        plan_data, error = self.plan_repo.load_plan()
        if error or not plan_data:
            return error or "Plan not found."
        task = self.plan_repo._find_task(plan_data, task_id)
        if not task:
            return f"Task not found: {task_id}"
        title = task.get("title") or task_id
        start = task.get("start") or "-"
        end = task.get("end") or "-"
        status = task.get("status", "pending")
        return f"{title} ({task_id}): {start}-{end}, status: {status}"

    def reschedule_remaining_day(self, current_task_id: str, delay_minutes: int) -> str:
        """Shift the current task and the rest of the day by given minutes."""
        if delay_minutes == 0:
            return "Delay is 0; no changes needed."
        plan_data, error = self.plan_repo.load_plan()
        if error or not plan_data:
            return error or "Plan not found."
        msg = self.plan_repo.shift_remaining(plan_data, current_task_id, delay_minutes)
        try:
            anchor = self.plan_repo._find_task(plan_data, current_task_id)
            if anchor and anchor.get("start") and anchor.get("end"):
                self.calendar.create_event(
                    title=anchor.get("title", current_task_id),
                    start_time=anchor["start"],
                    end_time=anchor["end"],
                    description="GuardianAgent auto-reschedule",
                )
        except Exception:
            msg += " | Calendar sync skipped."
        self.memory.write_memory("schedule_adjustments", f"{msg} | task={current_task_id}")
        return msg

    def suggest_micro_task(self, context: str = "") -> str:
        """Return a 5-minute micro task suggestion."""
        picks = list(self.micro_tasks)
        random.shuffle(picks)
        if context:
            picks.insert(0, f"For {context}: do only the first step, 5 minutes.")
        suggestion = picks[0]
        self.memory.write_memory("micro_task_hint", suggestion)
        return suggestion


class RewardSystemTool:
    """Dispense motivational rewards."""

    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo
        self._phrases_level1 = [
            "Task slayer!",
            "Dopamine fully charged!",
            "Achievement unlocked!",
            "Wrap it up and pocket the joy.",
            "Brain battery recharged - enjoy your reward!",
        ]
        self._phrases_level2 = [
            "The dragon is waiting. Return to the task and cut one piece.",
            "Hold for 5 minutes; your future self will thank you.",
            "The procrastination monster is near - scare it off with one action!",
        ]
        self._phrases_level3 = [
            "Strong finish. You were steady today.",
            "All-day report complete. Rare Easter egg unlocked.",
        ]

    def _cowsay(self, text: str, mood: str = "cow") -> str:
        if not cowsay:
            return text
        try:
            list_fn = getattr(cowsay, "list_cows", None)
            available = list_fn() if callable(list_fn) else ["cow", "tux", "dragon", "stegosaurus"]
            cow_name = mood if mood in available else random.choice(available)
            get_fn = getattr(cowsay, "get_output_string", None)
            if callable(get_fn):
                return get_fn(cow_name, text)
        except Exception:
            return text
        return text

    def dispense_reward(self, level: int = 1) -> str:
        """Dispense motivational reward (1=done,2=delay,3=end-of-day)."""
        plan_data, _ = self.plan_repo.load_plan()
        if level == 1:
            phrase = random.choice(self._phrases_level1)
            return self._cowsay(phrase, "cow")
        if level == 2:
            phrase = random.choice(self._phrases_level2)
            return self._cowsay(phrase, "dragon")
        report = self.plan_repo.day_summary(plan_data)
        phrase = random.choice(self._phrases_level3)
        today_path = os.path.join(PARKING_DIR, f"thought_parking_{datetime.date.today().isoformat()}.txt")
        parking = ""
        if os.path.exists(today_path):
            with open(today_path, "r") as f:
                parking = f.read().strip()
        reward_block = f"{phrase}\n{report}"
        if parking:
            reward_block += f"\n\nToday's thought parking:\n{parking}"
        return self._cowsay(reward_block, "stegosaurus")


# Shared instances
memory = Memory(memory_dir=os.path.join(ADHD_DIR, "memory"))
webfetch_tool = WebFetch(timeout=20)
calendar_tool = _safe_calendar()
plan_repo = PlanRepository(ADHD_DIR)

context_tool = ContextAwarenessTool(plan_repo)
thought_tool = ThoughtExpanderTool(plan_repo, memory, webfetch_tool)
schedule_tool = ScheduleManagerTool(plan_repo, memory, calendar_tool)
reward_tool = RewardSystemTool(plan_repo)


guardian_system_prompt = """
You are GuardianAgent, a strict yet caring ADHD time guardian.
Respond in English only, even if the user writes in another language.
- Always speak based on the real contents of daily_tasks_YYYY-MM-DD.json and handover_note.json. Never invent plans.
- Prefer tool use: ContextAwareness for current task, ThoughtExpander for thought parking, ScheduleManager for rescheduling, RewardSystem for rewards.
- Flow: ask how the start feels -> if smooth, stay in focus mode and log thoughts; if blocked, give 5-minute micro-tasks and use reschedule_remaining_day if needed; at the end, release rewards and show the thought parking summary.
- Tone: short, directive, encouraging. No long lectures.
""".strip()


class GuardianAgent(Agent):
    """Agent wrapper with predefined tools and prompt."""

    def __init__(self):
        tools = [
            context_tool,
            thought_tool,
            schedule_tool,
            reward_tool,
            webfetch_tool,
            memory,
            calendar_tool,
        ]
        super().__init__(
            name="guardian",
            tools=tools,
            system_prompt=guardian_system_prompt,
            model=resolve_model(),
            max_iterations=6,
            quiet=False,
        )


class GuardianLoop:
    """Main loop to interact with user via stdin/stdout."""

    def __init__(self, agent: GuardianAgent, plan_repo: PlanRepository):
        self.agent = agent
        self.plan_repo = plan_repo

    def _print_overview(self):
        plan_data, error = self.plan_repo.load_plan()
        now_text = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        print(f"\n⏱️ {now_text}")
        if error or not plan_data:
            print(f"⚠️ {error or 'Plan file not found'}")
            return
        plan_date = plan_data["plan_date"]
        tasks = plan_data["tasks"]
        print(f"🗂️ Loaded plan for {plan_date}, {len(tasks)} tasks:")
        for idx, task in enumerate(tasks, start=1):
            start = task.get("start") or "-"
            end = task.get("end") or "-"
            title = task.get("title") or f"Task {idx}"
            status = task.get("status", "pending")
            icon = "✅" if status == "done" else "⬜️"
            print(f"{icon} {idx}. {start}-{end} | {title} (id={task.get('id','?')})")
        status, focus_task = self.plan_repo.determine_focus(plan_data)
        if focus_task:
            title = focus_task.get("title") or "current task"
            print(f"🚦 Status: {status} | {title}")
        print("Are you started yet? Is it going smoothly?")

    def _maybe_end_of_day(self):
        plan_data, _ = self.plan_repo.load_plan()
        summary = reward_tool.dispense_reward(level=3)
        print("\n🌙 Day-end recap:")
        print(summary)
        if plan_data:
            self._write_handover_prompt(plan_data)

    def _write_handover_prompt(self, plan_data: Dict):
        print("\n📩 Leave a note for tomorrow's Planner? (enter to skip)")
        notes: List[str] = []
        while True:
            note = input("Note: ").strip()
            if not note:
                break
            notes.append(note)
            more = input("Add another? (y to continue, enter to finish): ").strip().lower()
            if not more.startswith("y"):
                break
        if not notes:
            return
        payload = {
            "date": plan_data.get("plan_date", datetime.date.today()).isoformat(),
            "content": notes,
            "status": "unread",
            "written_at": datetime.datetime.now().isoformat(),
        }
        with open(HANDOVER_NOTE_FILE, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Handover note saved: {HANDOVER_NOTE_FILE}")

    def run(self):
        print("🛡️ GuardianAgent started! Type 'q' to quit.")
        self._print_overview()
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in {"q", "quit", "exit"}:
                self._maybe_end_of_day()
                break
            response = self.agent.input(user_input)
            print(f"\nGuardian: {response}")
            # Simple distraction check: query active window each round
            window_info = context_tool.get_active_window()
            if window_info and "::" in window_info:
                app_name, title = window_info.split("::", 1)
                if title and app_name:
                    print(f"[Distraction Check] Active window: {app_name} - {title}")


def main():
    agent = GuardianAgent()
    loop = GuardianLoop(agent, plan_repo)
    loop.run()


if __name__ == "__main__":
    main()
