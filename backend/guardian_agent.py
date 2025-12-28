# guardian_agent.py
# Guardian Agent built on ConnectOnion with class-based tools and a check-in loop.

import datetime
import json
import os
import random
import subprocess
import textwrap
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from connectonion import Agent, Memory, WebFetch

try:
    from connectonion import GoogleCalendar
except Exception:
    GoogleCalendar = None  # type: ignore

try:
    import cowsay  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cowsay = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADHD_DIR = os.path.join(BASE_DIR, "adhd_brain")
os.makedirs(ADHD_DIR, exist_ok=True)

PARKING_DIR = os.path.join(ADHD_DIR, "thought_parking")
os.makedirs(PARKING_DIR, exist_ok=True)

HANDOVER_NOTE_FILE = os.path.join(ADHD_DIR, "handover_note.json")
UPDATED_PLAN_FILE = os.path.join(ADHD_DIR, "updated_tasks.json")

load_dotenv(os.path.join(BASE_DIR, ".env"))


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
            return None, f"未找到计划文件：{os.path.join(self.plan_dir, f'daily_tasks_{target_date}.json')}"
        try:
            with open(path, "r") as f:
                tasks = json.load(f)
        except Exception as exc:
            return None, f"读取计划失败：{exc}"
        if not isinstance(tasks, list):
            return None, "计划文件格式异常（应为列表）。"
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
        return f"计划已更新：{target_path}"

    def shift_remaining(self, plan_data: Dict, anchor_id: str, delay_minutes: int) -> str:
        normalized = plan_data.get("normalized") or []
        anchor = next((t for t in normalized if t.get("id") == anchor_id), None)
        if not anchor:
            return f"未找到任务 {anchor_id}"
        delta = datetime.timedelta(minutes=delay_minutes)
        plan_date = plan_data["plan_date"]
        anchor_end = anchor.get("end_dt") or anchor.get("start_dt") or datetime.datetime.now().astimezone()

        # 更新 anchor 结束时间
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
        return f"已顺延 {delay_minutes} 分钟，并重排后续任务。"

    def day_summary(self, plan_data: Optional[Dict]) -> str:
        if not plan_data:
            return "今日计划未加载。"
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
        return f"今天完成 {done}/{total} 项，专注 {hours} 小时。"


class ContextAwarenessTool:
    """感知当前环境与任务状态。"""

    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo

    def get_current_context(self) -> str:
        """Return current time, plan overview and focus task."""
        now = datetime.datetime.now().astimezone()
        plan_data, error = self.plan_repo.load_plan()
        header = now.strftime("当前时间：%Y-%m-%d %H:%M:%S %Z (UTC%z)")
        if error or not plan_data:
            return f"{header}\n{error or '未加载计划'}"
        status, task = self.plan_repo.determine_focus(plan_data)
        plan_date = plan_data["plan_date"]
        tasks = plan_data.get("tasks", [])
        lines = [header, f"计划日期：{plan_date}，任务数：{len(tasks)}", f"状态：{status}"]
        if task:
            start = task.get("start") or "-"
            end = task.get("end") or "-"
            title = task.get("title") or "当前任务"
            lines.append(f"聚焦：{title}（{start}-{end}）")
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
            return f"获取前台窗口失败：{exc}"
        if result.returncode != 0:
            return f"osascript 错误：{result.stderr.strip()}"
        return result.stdout.strip() or "未获取到前台窗口。"


class ThoughtExpanderTool:
    """处理念头停车场并自动扩展搜索。"""

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
            return "冬季保暖"
        if month in (6, 7, 8):
            return "夏季清凉"
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
            fetch_error = f"搜索失败：{exc}"
        else:
            fetch_error = ""

        lines = [f"念头：{thought}", f"搜索词：{query}"]
        if results:
            lines.append("结果：")
            for title, href in results:
                lines.append(f"- {title} | {href}")
        elif fetch_error:
            lines.append(fetch_error)
        else:
            lines.append("未找到有效结果，但已记录念头。")

        parking_path = self._parking_path()
        ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        record = f"[{ts}]\n" + "\n".join(lines) + "\n\n"
        with open(parking_path, "a") as f:
            f.write(record)

        memory_key = f"thought_{datetime.date.today().isoformat()}"
        self.memory.write_memory(memory_key, "\n".join(lines))
        return f"已记录到念头停车场（{parking_path}）。{fetch_error or '先专注当前任务，稍后再处理这些灵感。'}"


class ScheduleManagerTool:
    """管理任务进度与弹性重排。"""

    def __init__(self, plan_repo: PlanRepository, memory: Memory, calendar: object):
        self.plan_repo = plan_repo
        self.memory = memory
        self.calendar = calendar
        self.micro_tasks = [
            "只写开头的一句话",
            "打开文档，把标题敲出来",
            "整理桌面 3 分钟",
            "写下一条你要回答的问题",
            "只读一段参考资料",
            "把计时器设为 5 分钟，什么都不想，开始做",
            "给自己倒一杯水并回到座位",
        ]

    def check_task_status(self, task_id: str) -> str:
        """Check start/end/status for a task."""
        plan_data, error = self.plan_repo.load_plan()
        if error or not plan_data:
            return error or "未找到计划。"
        task = self.plan_repo._find_task(plan_data, task_id)
        if not task:
            return f"未找到任务 {task_id}"
        title = task.get("title") or task_id
        start = task.get("start") or "-"
        end = task.get("end") or "-"
        status = task.get("status", "pending")
        return f"{title}（{task_id}）：{start}-{end}，状态：{status}"

    def reschedule_remaining_day(self, current_task_id: str, delay_minutes: int) -> str:
        """Shift the current task and the rest of the day by given minutes."""
        if delay_minutes == 0:
            return "延迟为 0，无需调整。"
        plan_data, error = self.plan_repo.load_plan()
        if error or not plan_data:
            return error or "未找到计划。"
        msg = self.plan_repo.shift_remaining(plan_data, current_task_id, delay_minutes)
        try:
            anchor = self.plan_repo._find_task(plan_data, current_task_id)
            if anchor and anchor.get("start") and anchor.get("end"):
                self.calendar.create_event(
                    title=anchor.get("title", current_task_id),
                    start_time=anchor["start"],
                    end_time=anchor["end"],
                    description="GuardianAgent 自动重排",
                )
        except Exception:
            msg += " | 日历同步已跳过。"
        self.memory.write_memory("schedule_adjustments", f"{msg} | task={current_task_id}")
        return msg

    def suggest_micro_task(self, context: str = "") -> str:
        """Return a 5-minute micro task suggestion."""
        picks = list(self.micro_tasks)
        random.shuffle(picks)
        if context:
            picks.insert(0, f"针对 {context}：只做第一步，5 分钟即可。")
        suggestion = picks[0]
        self.memory.write_memory("micro_task_hint", suggestion)
        return suggestion


class RewardSystemTool:
    """发放情绪奖励。"""

    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo
        self._phrases_level1 = [
            "任务杀手！",
            "多巴胺满载！",
            "今日成就解锁！",
            "收工！把快乐装进口袋。",
            "大脑电量回满，去享受奖励吧！",
        ]
        self._phrases_level2 = [
            "龙在等你：回到任务上，砍掉一点就好。",
            "坚持 5 分钟，未来的你会感谢现在的你。",
            "拖延怪靠近中，快用一个动作把它吓跑！",
        ]
        self._phrases_level3 = [
            "收官拉满，今天的你很稳。",
            "全天战绩总结，解锁稀有彩蛋。",
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
            reward_block += f"\n\n今天的念头停车场：\n{parking}"
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
你是 GuardianAgent，一位既严厉又温柔的 ADHD 时间守护者。
- 始终基于 daily_tasks_YYYY-MM-DD.json 和 handover_note.json 的真实内容发言，禁止臆造计划。
- 优先调用工具执行：ContextAwareness 获取当前任务，ThoughtExpander 处理念头停车场，ScheduleManager 调整日程，RewardSystem 奖励。
- 工作流：启动问询顺利度 -> 顺利则进入专注监听，记录念头并提醒走神；阻滞则给出 5 分钟微任务，必要时调用 reschedule_remaining_day 顺延；收尾时释放奖励，并吐出念头停车场。
- 语气：简短指令式、鼓励，不做长篇说教。
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
            model="co/gemini-2.5-pro",
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
            print(f"⚠️ {error or '未找到计划文件'}")
            return
        plan_date = plan_data["plan_date"]
        tasks = plan_data["tasks"]
        print(f"🗂️ 读取到 {plan_date} 的计划，共 {len(tasks)} 条：")
        for idx, task in enumerate(tasks, start=1):
            start = task.get("start") or "-"
            end = task.get("end") or "-"
            title = task.get("title") or f"任务 {idx}"
            status = task.get("status", "pending")
            icon = "✅" if status == "done" else "⬜️"
            print(f"{icon} {idx}. {start}-{end} | {title} (id={task.get('id','?')})")
        status, focus_task = self.plan_repo.determine_focus(plan_data)
        if focus_task:
            title = focus_task.get("title") or "当前任务"
            print(f"🚦 状态：{status} | {title}")
        print("现在是计划启动阶段，是否已经开始？顺利吗？")

    def _maybe_end_of_day(self):
        plan_data, _ = self.plan_repo.load_plan()
        summary = reward_tool.dispense_reward(level=3)
        print("\n🌙 日结：")
        print(summary)
        if plan_data:
            self._write_handover_prompt(plan_data)

    def _write_handover_prompt(self, plan_data: Dict):
        print("\n📩 给明天的 Planner 留句话？（回车跳过）")
        notes: List[str] = []
        while True:
            note = input("留言：").strip()
            if not note:
                break
            notes.append(note)
            more = input("继续添加？(y 继续，其它键结束)：").strip().lower()
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
        print(f"已写入交接留言：{HANDOVER_NOTE_FILE}")

    def run(self):
        print("🛡️ GuardianAgent 已启动！输入 'q' 退出。")
        self._print_overview()
        while True:
            user_input = input("\n你: ").strip()
            if user_input.lower() in {"q", "quit", "exit"}:
                self._maybe_end_of_day()
                break
            response = self.agent.input(user_input)
            print(f"\n守护者: {response}")
            # 简易走神检测：每轮询问一次前台窗口
            window_info = context_tool.get_active_window()
            if window_info and "::" in window_info:
                app_name, title = window_info.split("::", 1)
                if title and app_name:
                    print(f"[走神检测] 当前前台：{app_name} - {title}")


def main():
    agent = GuardianAgent()
    loop = GuardianLoop(agent, plan_repo)
    loop.run()


if __name__ == "__main__":
    main()
