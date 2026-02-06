# backend/new_agent.py
# ADHD Guardian Agent (The Guardian)
#
# Purpose:
# - Read structured plans produced by the Tymebox planner (daily_tasks_*.json)
# - Provide micro-step starts at the beginning of each tymebox via TodoList
# - Handle thought parking during execution (background WebFetch + memory)
# - Monitor distraction (simple heartbeat), and release rewards + parking info at the end
#
# Run: python new_agent.py

import os
import json
import datetime
import random
from typing import Optional

from dotenv import load_dotenv
from connectonion import Agent, Memory, GoogleCalendar, TodoList, WebFetch
from rich.console import Console
from rich.panel import Panel
try:
    import cowsay
except Exception:
    cowsay = None

from agents.model_config import resolve_model
from core.paths import resolve_data_root

# --- Constants & paths ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADHD_DIR = resolve_data_root()
os.makedirs(ADHD_DIR, exist_ok=True)

PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

PARKING_LOT_FILE = os.path.join(ADHD_DIR, "parking_lot_buffer.md")
STATE_FILE = os.path.join(ADHD_DIR, "guardian_state.json")
HANDOVER_NOTE_FILE = os.path.join(ADHD_DIR, "handover_note.json")

console = Console()
_latest_plan_data = None
_victory_shown = False
_handover_written = False

VICTORY_ASCII = [
    r"""
         \   ^__^
          \  (oo)\_______
             (__)\       )\/\
                 ||----w |
                 ||     ||
    """,
    r"""
      /\_/\
     ( o.o )
      > ^ <
    """,
    r"""
          __
         / _)
  .-^^^-/ /
 __/       /
<__.|_|-|_|
    """,
    r"""
          __.-._   _.-.__
       .-`      '.'      `-.
     .'                     `.
    /    YODA SAYS:            \
   |   Do or do not. There is   |
   |          no try.           |
    \                           /
     `.                       .'
       `-._               _.-'
            `-..___..-'
    """,
]

VICTORY_PHRASES = [
    "Task slayer!",
    "Dopamine fully charged!",
    "Achievement unlocked!",
    "Wrap it up and pocket the joy.",
    "Brain battery recharged - go enjoy your reward!",
]

_COWSAY_COWS = [
    "cow",
    "tux",
    "dragon",
    "kitty",
    "stegosaurus",
]


# --- Utilities / Tools ---

def get_current_datetime() -> str:
    """Return current local time with timezone for agent awareness."""
    now = datetime.datetime.now().astimezone()
    return now.strftime("Current local time: %Y-%m-%d %H:%M:%S %Z (UTC%z)")


def _resolve_plan_path(date: Optional[str] = None) -> Optional[str]:
    """Locate plan file path: prefer today, else most recent saved plan."""
    target_date = date or datetime.date.today().isoformat()
    today_path = os.path.join(ADHD_DIR, f"daily_tasks_{target_date}.json")
    if os.path.exists(today_path):
        return today_path
    candidates = sorted(
        f for f in os.listdir(ADHD_DIR) if f.startswith("daily_tasks_") and f.endswith(".json")
    )
    if not candidates:
        return None
    return os.path.join(ADHD_DIR, candidates[-1])


def _plan_date_from_path(path: str) -> datetime.date:
    """Extract date from daily_tasks_YYYY-MM-DD.json; fallback to today."""
    try:
        return datetime.datetime.strptime(os.path.basename(path), "daily_tasks_%Y-%m-%d.json").date()
    except ValueError:
        return datetime.date.today()


def _parse_task_time(value: Optional[str], plan_date: datetime.date, tzinfo) -> Optional[datetime.datetime]:
    """Parse a time string into tz-aware datetime; fill date from plan_date."""
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
            time_part = datetime.datetime.strptime(value, fmt).time()
            return datetime.datetime.combine(plan_date, time_part).replace(tzinfo=tzinfo)
        except ValueError:
            continue
    return None


def _normalize_plan_tasks(tasks: list, plan_date: datetime.date) -> list:
    """Attach parsed start/end times for sorting and time-window checks."""
    tzinfo = datetime.datetime.now().astimezone().tzinfo
    normalized = []
    for task in tasks:
        start_dt = _parse_task_time(task.get("start"), plan_date, tzinfo)
        end_dt = _parse_task_time(task.get("end"), plan_date, tzinfo)
        normalized.append({**task, "start_dt": start_dt, "end_dt": end_dt})
    normalized.sort(key=lambda t: t["start_dt"] or datetime.datetime.max.replace(tzinfo=tzinfo))
    return normalized


def load_plan_for_startup(date: Optional[str] = None):
    """Load and parse plan, returning structured data or error."""
    path = _resolve_plan_path(date)
    if not path:
        target_date = date or datetime.date.today().isoformat()
        expected = os.path.join(ADHD_DIR, f"daily_tasks_{target_date}.json")
        return None, f"Plan file not found: {expected}"
    try:
        with open(path, "r") as f:
            tasks = json.load(f)
    except Exception as exc:
        return None, f"Failed to read plan ({path}): {exc}"
    if not isinstance(tasks, list):
        return None, f"Invalid plan format (expected list): {path}"
    plan_date = _plan_date_from_path(path)
    normalized = _normalize_plan_tasks(tasks, plan_date)
    plan_data = {"path": path, "plan_date": plan_date, "tasks": tasks, "normalized_tasks": normalized}
    global _latest_plan_data
    _latest_plan_data = plan_data
    return (plan_data, None)


def _format_dt(dt_value: Optional[datetime.datetime], plan_date: datetime.date) -> str:
    """Format time; include date if not today."""
    if not dt_value:
        return "no time set"
    today = datetime.date.today()
    show_full_date = dt_value.date() != plan_date or plan_date != today
    fmt = "%Y-%m-%d %H:%M" if show_full_date else "%H:%M"
    return dt_value.strftime(fmt)


def _determine_focus_task(normalized_tasks: list):
    """Return focus status and task based on current time."""
    if not normalized_tasks:
        return "empty", None
    now = datetime.datetime.now().astimezone()
    timed_tasks = [t for t in normalized_tasks if t.get("start_dt")]
    if not timed_tasks:
        return "no_timed", normalized_tasks[0]
    for task in timed_tasks:
        start_dt = task["start_dt"]
        end_dt = task.get("end_dt") or start_dt
        if start_dt <= now <= end_dt:
            return "current", task
        if start_dt > now:
            return "upcoming", task
    return "finished", timed_tasks[-1]


def _parse_parking_lot_entries() -> list:
    """Extract parking lot entries (strip timestamps)."""
    if not os.path.exists(PARKING_LOT_FILE):
        return []
    with open(PARKING_LOT_FILE, "r") as f:
        content = f.read().strip()
    if not content:
        return []
    entries = []
    for block in content.split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("[") and "]" in lines[0]:
            lines = lines[1:]
        if not lines:
            continue
        entries.append(" ".join(lines))
    return entries


def _get_last_timed_end(normalized_tasks: list) -> Optional[datetime.datetime]:
    """Get the end time of the last timed task."""
    timed = [t for t in normalized_tasks if t.get("start_dt") or t.get("end_dt")]
    if not timed:
        return None
    last = timed[-1]
    return last.get("end_dt") or last.get("start_dt")


def _is_plan_finished(plan_data: dict) -> bool:
    """Check if current time is past the last task end."""
    last_end = _get_last_timed_end(plan_data.get("normalized_tasks", []))
    if not last_end:
        return False
    now = datetime.datetime.now().astimezone()
    return now > last_end


def _build_daily_report(plan_data: dict) -> str:
    """Build a daily recap report."""
    tasks = plan_data.get("tasks", [])
    normalized = plan_data.get("normalized_tasks", [])
    total_tasks = len(tasks)

    minutes = 0
    for task in normalized:
        start = task.get("start_dt")
        end = task.get("end_dt") or start
        if start and end:
            delta = (end - start).total_seconds() / 60
            if delta > 0:
                minutes += delta
    hours_text = f"{minutes/60:.1f}".rstrip("0").rstrip(".") or "0"

    report_lines = [f"You focused for {hours_text} hours and cleared {total_tasks} tasks today."]

    parking_entries = _parse_parking_lot_entries()
    if parking_entries:
        joined = "; ".join(parking_entries)
        report_lines.append(f"You resisted {len(parking_entries)} distractions: {joined}")
        report_lines.append("Mindset: these are your delayed-gratification trophies. You can do them now!")
    else:
        report_lines.append("No parked thoughts today. Focus at max power!")

    return "\n".join(report_lines)


def _victory_lap_text(plan_data: dict) -> str:
    phrase = random.choice(VICTORY_PHRASES)
    report = _build_daily_report(plan_data)

    # Try cowsay with random character; fallback to built-in ASCII.
    art = random.choice(VICTORY_ASCII)
    if cowsay:
        try:
            list_fn = getattr(cowsay, "list_cows", None)
            available_all = list_fn() if callable(list_fn) else _COWSAY_COWS
            available = [c for c in _COWSAY_COWS if c in available_all] or available_all
            cow_name = random.choice(available) if available else "cow"
            get_fn = getattr(cowsay, "get_output_string", None)
            if callable(get_fn):
                art = get_fn(cow_name, phrase)
            else:
                cow_fn = getattr(cowsay, cow_name, None)
                if callable(cow_fn):
                    art = cow_fn(phrase)
        except Exception:
            art = random.choice(VICTORY_ASCII)

    return f"{art}\n\n{report}"


def show_victory_lap(plan_data: dict) -> None:
    """ASCII victory lap display."""
    text = _victory_lap_text(plan_data)
    console.print(Panel(text, title="Victory Lap", border_style="green", expand=True))


def write_handover_note(contents: list[str]) -> str:
    payload = {
        "date": datetime.date.today().isoformat(),
        "content": contents,
        "status": "unread",
    }
    with open(HANDOVER_NOTE_FILE, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return f"Handover note saved ({len(contents)} items): {HANDOVER_NOTE_FILE}"


def prompt_handover_note() -> None:
    """Collect handover notes and write to handover_note.json."""
    global _handover_written
    if _handover_written:
        return
    notes: list[str] = []
    print("\n📩 Any notes for tomorrow's Planner? e.g., 'wake up early' or 'add unfinished paper work'?")
    while True:
        note = input("Note (enter to skip): ").strip()
        if not note:
            if not notes:
                print("Skipped.")
            break
        notes.append(note)
        print(f"Saved: {note}")
        more = input("Add another? y to continue, enter to finish: ").strip().lower()
        if not more.startswith("y"):
            break
    _handover_written = True
    if not notes:
        return
    path_msg = write_handover_note(notes)
    print(path_msg)


def maybe_handle_completion(plan_data: Optional[dict] = None) -> None:
    """If all tasks finished, trigger victory lap + recap + handover."""
    global _victory_shown
    data = plan_data
    if data is None:
        data, _ = load_plan_for_startup()
    if not data or _victory_shown:
        return
    if not _is_plan_finished(data):
        return
    _victory_shown = True
    show_victory_lap(data)
    prompt_handover_note()


def read_structured_plan(date: Optional[str] = None) -> str:
    """
    Read the structured plan saved by the Tymebox planner.
    Args:
        date: optional, YYYY-MM-DD; default is today.
    Returns:
        Plan JSON string or error message.
    """
    path = _resolve_plan_path(date)
    if not path:
        target_date = date or datetime.date.today().isoformat()
        return f"Plan file not found: {os.path.join(ADHD_DIR, f'daily_tasks_{target_date}.json')}"
    with open(path, "r") as f:
        return f.read()


def append_parking_lot(entry: str) -> str:
    """Append a parking lot entry (timestamp + text)."""
    ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    with open(PARKING_LOT_FILE, "a") as f:
        f.write(f"[{ts}]\n{entry}\n\n")
    return f"Logged to parking lot: {PARKING_LOT_FILE}"


def read_parking_lot() -> str:
    """Read parking lot contents."""
    if not os.path.exists(PARKING_LOT_FILE):
        return "Parking lot is empty."
    with open(PARKING_LOT_FILE, "r") as f:
        return f.read()


def clear_parking_lot() -> str:
    """Clear parking lot contents."""
    if os.path.exists(PARKING_LOT_FILE):
        os.remove(PARKING_LOT_FILE)
    return "Parking lot cleared."


# --- Parking lot TodoList wrappers (avoid tool name conflicts) ---

def parking_add(content: str, active_form: Optional[str] = None) -> str:
    """Add an item to the parking lot TodoList."""
    return todo_parking.add(content, active_form or content)


def parking_complete(content: str) -> str:
    """Complete a parking lot Todo item."""
    return todo_parking.complete(content)


def parking_list() -> str:
    """List parking lot Todos."""
    return todo_parking.list()


def parking_clear() -> str:
    """Clear parking lot TodoList."""
    return todo_parking.clear()


def set_guardian_state(state: str) -> str:
    """Set guardian state."""
    payload = {"state": state, "updated_at": datetime.datetime.now().isoformat()}
    with open(STATE_FILE, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return f"State updated: {state}"


def get_guardian_state() -> str:
    """Get current guardian state."""
    if not os.path.exists(STATE_FILE):
        return "state: Idle"
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
    return f"state: {data.get('state', 'Idle')} (updated_at: {data.get('updated_at')})"


def announce_plan_on_startup() -> None:
    """Announce today's plan and first action on startup."""
    plan_data, error = load_plan_for_startup()
    print(f"\n⏱️ {get_current_datetime()}")
    if error:
        print(f"⚠️ {error}")
        print("Tip: generate a plan first (daily_tasks_YYYY-MM-DD.json).")
        return

    plan_date = plan_data["plan_date"]
    tasks = plan_data["tasks"]
    normalized = plan_data["normalized_tasks"]
    file_name = os.path.basename(plan_data["path"])

    print(f"🗂️ Loaded plan for {plan_date} ({file_name}), {len(tasks)} tasks:")
    for idx, task in enumerate(tasks, start=1):
        start = task.get("start") or "-"
        end = task.get("end") or "-"
        title = task.get("title") or "Untitled task"
        print(f"{idx}. {start} -> {end} | {title}")

    today = datetime.date.today()
    if plan_date != today:
        print(f"Note: plan date {plan_date} differs from today {today}.")

    status, focus_task = _determine_focus_task(normalized)
    if status == "current":
        title = focus_task.get("title") or "current task"
        start_text = _format_dt(focus_task.get("start_dt"), plan_date)
        end_text = _format_dt(focus_task.get("end_dt") or focus_task.get("start_dt"), plan_date)
        print(f"🚦 You should be working on: {title} ({start_text}-{end_text})")
    elif status == "upcoming":
        title = focus_task.get("title") or "next task"
        start_text = _format_dt(focus_task.get("start_dt"), plan_date)
        print(f"⏭️ Next at {start_text}: {title}")
    elif status == "finished":
        title = focus_task.get("title") or "last task"
        end_text = _format_dt(focus_task.get("end_dt") or focus_task.get("start_dt"), plan_date)
        print(f"✅ Timed plan finished. Last task: {title} (ended {end_text})")
    elif status == "no_timed":
        title = focus_task.get("title") or "task"
        print(f"📝 Plan has no times. Start with: {title}")
    else:
        print("⚠️ Plan is empty. Please create today's tymebox first.")

    maybe_handle_completion(plan_data)


def ask_start_smoothness(plan_data: Optional[dict] = None) -> None:
    """Ask if starting is smooth to decide whether to trigger micro-steps."""
    if _victory_shown:
        return
    data = plan_data or _latest_plan_data
    if data and _is_plan_finished(data):
        return
    print("\n👋 Is the start going smoothly? Any tasks feel resistant?")
    print("If it is smooth, just go. If you're stuck, we'll use 5-minute micro-steps.")


class ActivityMonitor:
    """
    Simple distraction monitor: record last activity and check idle time.
    For real mouse monitoring, integrate pynput on top.
    """

    def __init__(self, idle_minutes: int = 5):
        self.idle_threshold = datetime.timedelta(minutes=idle_minutes)
        self.last_activity = datetime.datetime.now()

    def heartbeat(self, note: str = "") -> str:
        self.last_activity = datetime.datetime.now()
        suffix = f" | {note}" if note else ""
        return f"Activity recorded: {self.last_activity.isoformat()}{suffix}"

    def check_idle(self) -> str:
        delta = datetime.datetime.now() - self.last_activity
        if delta >= self.idle_threshold:
            minutes = round(delta.total_seconds() / 60, 1)
            return f"idle: {minutes} min (above threshold)"
        return "active"


class ParkingTodoList(TodoList):
    """Dedicated TodoList for parking lot thoughts."""
    pass


# --- Init tools ---

memory = Memory(memory_dir=os.path.join(ADHD_DIR, "long_term_memory"))
calendar = GoogleCalendar()
todo_main = TodoList()             # main tasks / micro-steps
todo_parking = ParkingTodoList()   # parking lot Todos
webfetch = WebFetch(timeout=20)    # silent search
activity_monitor = ActivityMonitor(idle_minutes=8)


# --- System prompt ---

guardian_system_prompt = """
You are the ADHD Guardian Agent - a backstage execution coach.
Respond in English only, even if the user writes in another language.
Your goal: during tymebox execution, use visible progress + gentle nudges to help the user finish tasks.

## No hallucinations / boundaries
- Only speak based on the plan returned by `read_structured_plan()`; never invent new tasks or future plans.
- If the plan file is missing/unreadable, say so and ask the user to generate a plan in the Planner; do not guess.
- Do not create tomorrow's plan or alter task titles on your own.
- If the user asks for a new/tomorrow plan, reply: "I'm the execution guardian. Use the Planner to schedule."

## State machine (keep state file in sync)
- Idle: waiting for the next tymebox.
- Starting: time reached but user hasn't started; launch micro-steps via TodoList.
- Running: focus in progress; use thought parking and distraction monitoring.
- Closing: wrap up, celebrate, and release parking lot contents.
Use `set_guardian_state` / `get_guardian_state` explicitly.

## Inputs / data sources
- `read_structured_plan()`: read Agent A's JSON plan. Prefer tymebox names and start/end times.
- `get_current_datetime()`: report time and sense date.

## Core flow
0) Pre-start check
   - First question: "Is the start going smoothly? Any tasks feel resistant?"
   - If the user says it is smooth/already started, do not repeat "just do 5 minutes";
     only use that for stuck/resistant/procrastination cases.

1) Micro-step kickoff (Starting)
   - If the user is stuck: TodoList.clear(), generate 3-5 tiny actions, call add()/start(),
     and complete step by step.
   - Remind stuck tasks: "Just do 5 minutes." Do not repeat for smooth tasks.

2) Thought parking (Running)
   - For off-topic requests, do not respond with results immediately.
   - If search is needed, use WebFetch.fetch()/strip_tags()/analyze_page(), then write summaries
     into `append_parking_lot` or todo_parking.
   - Reply: "Logged and searched. Stay on the current task; results are in the parking lot."

3) Distraction monitoring
   - Periodically call activity_monitor.check_idle(); if idle, remind:
     "You still have <current item> on the TodoList - want to finish it?"

4) Closing
   - Show TodoList progress; praise the user; call read_parking_lot() then clear_parking_lot().
   - For unfinished tasks: suggest "move to tomorrow" to avoid perfectionism.

5) Calendar sync / adjustments
   - If the user asks to change/delete schedule, call GoogleCalendar tools (respect timezone).

## Tone
- Warm, encouraging, short and directive; avoid long lectures.
- Prefer action (call tools), minimize filler.
""".strip()


# --- Create agent ---

guardian_agent = Agent(
    name="adhd_guardian",
    model=resolve_model(),
    system_prompt=guardian_system_prompt,
    tools=[
        memory,
        todo_main,
        webfetch,
        activity_monitor,
        read_structured_plan,
        append_parking_lot,
        read_parking_lot,
        clear_parking_lot,
        parking_add,
        parking_complete,
        parking_list,
        parking_clear,
        set_guardian_state,
        get_guardian_state,
        get_current_datetime,
        calendar,
    ],
)


# --- Entry point ---

def main():
    print("🛡️ ADHD Guardian Agent started! (type 'q' to quit)")
    print("Tip: generate a plan first with Agent A (the Planner), then let me execute.")
    announce_plan_on_startup()
    ask_start_smoothness(_latest_plan_data)
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["q", "quit", "exit"]:
            break
        response = guardian_agent.input(user_input)
        print(f"\nGuardian: {response}")
        maybe_handle_completion()


if __name__ == "__main__":
    main()
