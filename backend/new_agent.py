# backend/new_agent.py
# ADHD 专注力守护者 (The Guardian Agent)
#
# 作用：
# - 读取时间盒教练生成的结构化计划（daily_tasks_*.json）
# - 在每个时间盒开始时，用 TodoList 做微步启动
# - 运行中处理“念头停车场”（后台 WebFetch + 记忆存储）
# - 监控走神（简易心跳），收尾时释放奖励与停车场信息
#
# 运行方式：python new_agent.py

import os
import json
import datetime
from typing import Optional

from dotenv import load_dotenv
from connectonion import Agent, Memory, GoogleCalendar, TodoList, WebFetch

# --- 常量与路径 ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADHD_DIR = os.path.join(BASE_DIR, "adhd_brain")
os.makedirs(ADHD_DIR, exist_ok=True)

load_dotenv(os.path.join(BASE_DIR, ".env"))

PARKING_LOT_FILE = os.path.join(ADHD_DIR, "parking_lot_buffer.md")
STATE_FILE = os.path.join(ADHD_DIR, "guardian_state.json")


# --- 工具函数 / 工具类 ---

def get_current_datetime() -> str:
    """返回当前本地时间，包含时区，供 Agent 感知。"""
    now = datetime.datetime.now().astimezone()
    return now.strftime("当前本地时间：%Y-%m-%d %H:%M:%S %Z (UTC%z)")


def _resolve_plan_path(date: Optional[str] = None) -> Optional[str]:
    """定位计划文件路径，优先今天，其次最近一次保存的计划。"""
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
    """从 daily_tasks_YYYY-MM-DD.json 提取日期，失败则回退到今天。"""
    try:
        return datetime.datetime.strptime(os.path.basename(path), "daily_tasks_%Y-%m-%d.json").date()
    except ValueError:
        return datetime.date.today()


def _parse_task_time(value: Optional[str], plan_date: datetime.date, tzinfo) -> Optional[datetime.datetime]:
    """将时间字符串解析为带时区的 datetime，用计划日期补全缺失的日期。"""
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
    """为任务补齐解析后的开始/结束时间，便于排序和判断当前时间段。"""
    tzinfo = datetime.datetime.now().astimezone().tzinfo
    normalized = []
    for task in tasks:
        start_dt = _parse_task_time(task.get("start"), plan_date, tzinfo)
        end_dt = _parse_task_time(task.get("end"), plan_date, tzinfo)
        normalized.append({**task, "start_dt": start_dt, "end_dt": end_dt})
    normalized.sort(key=lambda t: t["start_dt"] or datetime.datetime.max.replace(tzinfo=tzinfo))
    return normalized


def load_plan_for_startup(date: Optional[str] = None):
    """读取并解析计划，返回结构化数据和错误信息（二者之一）。"""
    path = _resolve_plan_path(date)
    if not path:
        target_date = date or datetime.date.today().isoformat()
        expected = os.path.join(ADHD_DIR, f"daily_tasks_{target_date}.json")
        return None, f"未找到计划文件：{expected}"
    try:
        with open(path, "r") as f:
            tasks = json.load(f)
    except Exception as exc:
        return None, f"读取计划失败（{path}）：{exc}"
    if not isinstance(tasks, list):
        return None, f"计划格式异常（期望列表）：{path}"
    plan_date = _plan_date_from_path(path)
    normalized = _normalize_plan_tasks(tasks, plan_date)
    return (
        {"path": path, "plan_date": plan_date, "tasks": tasks, "normalized_tasks": normalized},
        None,
    )


def _format_dt(dt_value: Optional[datetime.datetime], plan_date: datetime.date) -> str:
    """友好格式化时间，若与今日日期不符则包含日期。"""
    if not dt_value:
        return "未标时间"
    today = datetime.date.today()
    show_full_date = dt_value.date() != plan_date or plan_date != today
    fmt = "%Y-%m-%d %H:%M" if show_full_date else "%H:%M"
    return dt_value.strftime(fmt)


def _determine_focus_task(normalized_tasks: list):
    """基于当前时间返回状态与要关注的任务。"""
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


def read_structured_plan(date: Optional[str] = None) -> str:
    """
    读取时间盒教练保存的结构化计划。
    Args:
        date: 可选，格式 YYYY-MM-DD；为空则读取今天。
    Returns:
        计划 JSON 字符串或错误提示。
    """
    path = _resolve_plan_path(date)
    if not path:
        target_date = date or datetime.date.today().isoformat()
        return f"未找到计划文件：{os.path.join(ADHD_DIR, f'daily_tasks_{target_date}.json')}"
    with open(path, "r") as f:
        return f.read()


def append_parking_lot(entry: str) -> str:
    """将念头停车场条目写入缓冲文件（时间戳 + 文本）。"""
    ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    with open(PARKING_LOT_FILE, "a") as f:
        f.write(f"[{ts}]\n{entry}\n\n")
    return f"已记录到停车场：{PARKING_LOT_FILE}"


def read_parking_lot() -> str:
    """读取念头停车场内容。"""
    if not os.path.exists(PARKING_LOT_FILE):
        return "停车场为空。"
    with open(PARKING_LOT_FILE, "r") as f:
        return f.read()


def clear_parking_lot() -> str:
    """清空念头停车场。"""
    if os.path.exists(PARKING_LOT_FILE):
        os.remove(PARKING_LOT_FILE)
    return "停车场已清空。"


# --- 停车场 TodoList 的代理函数（避免工具名冲突） ---

def parking_add(content: str, active_form: Optional[str] = None) -> str:
    """向停车场 TodoList 添加一项。active_form 为空则复用 content。"""
    return todo_parking.add(content, active_form or content)


def parking_complete(content: str) -> str:
    """完成停车场 Todo 项。"""
    return todo_parking.complete(content)


def parking_list() -> str:
    """列出停车场 Todo。"""
    return todo_parking.list()


def parking_clear() -> str:
    """清空停车场 TodoList。"""
    return todo_parking.clear()


def set_guardian_state(state: str) -> str:
    """设置状态机当前状态。"""
    payload = {"state": state, "updated_at": datetime.datetime.now().isoformat()}
    with open(STATE_FILE, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return f"状态已更新为：{state}"


def get_guardian_state() -> str:
    """读取状态机当前状态。"""
    if not os.path.exists(STATE_FILE):
        return "state: Idle"
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
    return f"state: {data.get('state', 'Idle')} (updated_at: {data.get('updated_at')})"


def announce_plan_on_startup() -> None:
    """启动时自动汇报今日计划与首个动作。"""
    plan_data, error = load_plan_for_startup()
    print(f"\n⏱️ {get_current_datetime()}")
    if error:
        print(f"⚠️ {error}")
        print("提示：先用时间盒教练生成计划 (daily_tasks_YYYY-MM-DD.json)。")
        return

    plan_date = plan_data["plan_date"]
    tasks = plan_data["tasks"]
    normalized = plan_data["normalized_tasks"]
    file_name = os.path.basename(plan_data["path"])

    print(f"🗂️ 读取到 {plan_date} 的计划（{file_name}），共 {len(tasks)} 条：")
    for idx, task in enumerate(tasks, start=1):
        start = task.get("start") or "-"
        end = task.get("end") or "-"
        title = task.get("title") or "未命名任务"
        print(f"{idx}. {start} -> {end} | {title}")

    today = datetime.date.today()
    if plan_date != today:
        print(f"提醒：计划日期为 {plan_date}，与当前日期 {today} 不同。")

    status, focus_task = _determine_focus_task(normalized)
    if status == "current":
        title = focus_task.get("title") or "当前任务"
        start_text = _format_dt(focus_task.get("start_dt"), plan_date)
        end_text = _format_dt(focus_task.get("end_dt") or focus_task.get("start_dt"), plan_date)
        print(f"🚦 现在应该在做：{title}（{start_text}-{end_text}）")
    elif status == "upcoming":
        title = focus_task.get("title") or "下一任务"
        start_text = _format_dt(focus_task.get("start_dt"), plan_date)
        print(f"⏭️ 下一步 {start_text} 开始：{title}")
    elif status == "finished":
        title = focus_task.get("title") or "最后任务"
        end_text = _format_dt(focus_task.get("end_dt") or focus_task.get("start_dt"), plan_date)
        print(f"✅ 计划时间段已结束。最后一项是：{title}（结束于 {end_text}）")
    elif status == "no_timed":
        title = focus_task.get("title") or "任务"
        print(f"📝 计划未写时间，从第一个任务开始：{title}")
    else:
        print("⚠️ 计划为空，请先生成今天的时间盒。")


class ActivityMonitor:
    """
    简易走神监控：用“心跳”记录最近一次活动时间，检查是否超时。
    如果需要真实的鼠标监听，可在此基础上接入 pynput。
    """

    def __init__(self, idle_minutes: int = 5):
        self.idle_threshold = datetime.timedelta(minutes=idle_minutes)
        self.last_activity = datetime.datetime.now()

    def heartbeat(self, note: str = "") -> str:
        self.last_activity = datetime.datetime.now()
        suffix = f" | {note}" if note else ""
        return f"已记录活动时间：{self.last_activity.isoformat()}{suffix}"

    def check_idle(self) -> str:
        delta = datetime.datetime.now() - self.last_activity
        if delta >= self.idle_threshold:
            minutes = round(delta.total_seconds() / 60, 1)
            return f"idle: {minutes} min (超过阈值)"
        return "active"


class ParkingTodoList(TodoList):
    """专用于念头停车场的 TodoList，避免与主 TodoList 重名。"""
    pass


# --- 初始化工具 ---

memory = Memory(memory_dir="adhd_brain")
calendar = GoogleCalendar()
todo_main = TodoList()             # 主任务/微步启动
todo_parking = ParkingTodoList()   # 停车场 Todo（独立类名，避免注册冲突）
webfetch = WebFetch(timeout=20)    # 静默搜索
activity_monitor = ActivityMonitor(idle_minutes=8)


# --- 系统提示词 ---

guardian_system_prompt = """
你是 “ADHD 专注力守护者 (The Guardian Agent)” —— 一个常驻后台的执行教练。
你的目标：在时间盒执行期，用可视化进度与温柔提醒，陪伴用户完成任务。

## 状态机 (保持状态文件同步)
- Idle：等待下一个时间盒。
- Starting：时间到但用户未动，启动“微步”引导，使用 TodoList 清单。
- Running：专注进行中，开启念头停车场与走神检测。
- Closing：收尾，庆祝并释放停车场内容。
使用 `set_guardian_state` / `get_guardian_state` 显式标记状态。

## 输入/数据来源
- `read_structured_plan()`：读取 Agent A 的 JSON 计划。优先使用时间盒名称、起止时间。
- `get_current_datetime()`：报时、感知当前日期。

## 核心玩法
1) 微步启动 (Starting)
   - 当任务开始但用户迟疑：TodoList.clear()，生成 3-5 个超小起步动作，调用 add()/start()，逐项 complete()。
   - 提醒：“只做 5 分钟就好”。

2) 念头停车场 (Running)
   - 离题请求：不要立刻喂结果。
   - 若需搜索，后台用 WebFetch.fetch()/strip_tags()/analyze_page()，摘要写入 `append_parking_lot` 或 todo_parking。
   - 回复用户：“我记下并查好了，先专注当前任务，结果在停车场等你。”

3) 走神检测
   - 周期性调用 activity_monitor.check_idle()；超时提醒：“还没勾掉 TodoList 上的 <当前项>，要不要卡点完成？”

4) 收尾 (Closing)
   - 展示 TodoList 进度；肯定用户；调用 read_parking_lot() 释放停车场内容，再 clear_parking_lot()。
   - 未完成任务：建议标记“移至明天”，避免完美主义。

5) 日程同步/调整
   - 如用户要求修改/删除日程，可调用 GoogleCalendar 对应接口（保持正确时区）。

## 语气
- 温柔、鼓励、简短指令式，避免长篇说教。
- 优先行动（调用工具），减少空话。
""".strip()


# --- 创建 Agent ---

guardian_agent = Agent(
    name="adhd_guardian",
    model="co/gemini-2.5-pro",
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


# --- 运行入口 ---

def main():
    print("🛡️ ADHD 专注力守护者已启动！(输入 'q' 退出)")
    print("提示：先用 Agent A (时间盒教练) 生成计划，再让我来执行。")
    announce_plan_on_startup()
    while True:
        user_input = input("\n你: ")
        if user_input.lower() in ["q", "quit", "exit"]:
            break
        response = guardian_agent.input(user_input)
        print(f"\n守护者: {response}")


if __name__ == "__main__":
    main()
