# ADHD Tymebox FastAPI 后端设计方案

> 版本：v1.0
> 日期：2026-01-26
> 目标：桌面端本地服务（单用户）

---

## 一、项目背景

### 1.1 产品流程概述

1. **任务规划阶段**：用户告诉主 Agent 当天要做的事，PlannerAgent 使用时间盒管理法规划任务，生成 JSON 并同步到 Google Calendar
2. **专注执行阶段**：FocusAgent 运行时，IdleWatcher 每 30s 检测走神行为（空闲/无关窗口），触发提醒
3. **念头停车场**：执行任务中用户可记录突发想法，任务完成后汇总并执行调查，发放奖励（cowsay）

### 1.2 设计目标

- 将 CLI 模式的 Agent 系统接入 FastAPI，为未来桌面 UI 提供 HTTP/SSE 接口
- **单用户本地服务**：简化架构，无需复杂的会话管理
- 复用 ConnectOnion 框架现有的 Google OAuth 流程

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Desktop App (Electron/Tauri)               │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│   │  Task List  │  │  Chat UI    │  │  Focus Mode Dashboard   │ │
│   └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
└──────────┼────────────────┼─────────────────────┼───────────────┘
           │ GET            │ POST                │ SSE
           ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Server (:8000)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  API Endpoints:                                          │   │
│  │  • POST /api/chat          → 对话（路由到 Orchestrator） │   │
│  │  • GET  /api/tasks         → 获取任务清单                │   │
│  │  • PATCH /api/tasks/{id}   → 更新任务状态                │   │
│  │  • GET  /api/events        → SSE 实时推送（走神提醒等）  │   │
│  │  • GET  /api/focus/state   → 获取当前专注状态            │   │
│  │  • POST /api/auth/google   → 触发 Google OAuth           │   │
│  │  • GET  /api/auth/status   → 检查授权状态                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │              Application State (单例)                     │  │
│  │  • orchestrator: OrchestratorAgent                        │  │
│  │  • idle_watcher: IdleWatcher                              │  │
│  │  • event_queue: asyncio.Queue (SSE 推送队列)              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │              Multi-Agent System (现有)                    │  │
│  │  OrchestratorAgent → PlannerAgent / FocusAgent / Reward   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │              Background Services                          │  │
│  │  • IdleWatcher (后台线程，30s 检测间隔)                   │  │
│  │  • ParkingService (异步搜索)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、API 接口设计

### 3.1 对话接口

**`POST /api/chat`**

主要对话入口，所有用户消息都通过此接口发送。

```python
# Request
{
    "message": "今天要做三件事：写文档、开会、review代码"
}

# Response
{
    "content": "好的，我来帮你规划今天的任务...",
    "status": "CONTINUE" | "FINISHED",  # 会话状态
    "agent": "planner" | "focus" | "orchestrator",  # 当前处理的 agent
    "tasks_updated": true,  # 提示前端是否需要刷新任务列表
    "ascii_art": "..."  # 如果有 cowsay 奖励，原样返回
}
```

**实现要点**：
- 调用 `orchestrator.route(message)`
- `locked_agent` 状态由 OrchestratorAgent 内部管理，无需额外处理
- 检测响应中的 `<<FINISHED>>` 标记判断会话状态
- 如果响应包含 ASCII art（cowsay），需要完整保留

### 3.2 任务清单接口

**`GET /api/tasks`**

获取指定日期的任务列表。

```python
# Request
GET /api/tasks?date=2026-01-26  # 可选，默认今天

# Response
{
    "date": "2026-01-26",
    "tasks": [
        {
            "id": "task_xxx_0",
            "title": "深度工作：撰写技术文档",
            "start": "09:00",
            "end": "10:00",
            "type": "work",      # work / break / health
            "status": "pending", # pending / done
            "google_event_id": "abc123"
        }
    ],
    "summary": {
        "total": 8,
        "done": 3,
        "pending": 5
    }
}
```

**实现要点**：
- 直接读取 `backend/adhd_brain/daily_tasks_YYYY-MM-DD.json`
- 使用 `PlanManager._load_tasks()` 或直接读取 JSON 文件

### 3.3 任务状态更新接口

**`PATCH /api/tasks/{task_id}`**

前端直接标记任务完成（不经过对话）。

```python
# Request
PATCH /api/tasks/task_xxx_0
{
    "status": "done"
}

# Response
{
    "success": true,
    "task": {...},  # 更新后的任务对象
    "reward": "..."  # 如果是完成任务，返回 cowsay ASCII art
}
```

**实现要点**：
- 更新 JSON 文件中对应任务的 `status`
- 如果标记为 `done`，调用 `RewardToolkit` 生成奖励
- 同步更新 Google Calendar（可选）

### 3.4 专注状态接口

**`GET /api/focus/state`**

获取当前专注状态，供前端 Dashboard 显示。

```python
# Response
{
    "status": "current" | "upcoming" | "finished" | "no_plan",
    "active_task": {
        "id": "task_xxx",
        "title": "撰写技术文档",
        "start": "09:00",
        "end": "10:00",
        "remaining_minutes": 25
    },
    "progress": {
        "done": 3,
        "total": 8
    },
    "active_window": "VSCode - design.md",  # 当前活动窗口
    "idle_seconds": 45  # 空闲时长
}
```

**实现要点**：
- 调用 `ContextTool.get_focus_state()`
- 调用 `ContextTool.get_active_window()` 和 `get_idle_seconds()`

### 3.5 实时事件推送（SSE）

**`GET /api/events`**

使用 Server-Sent Events 推送实时事件到前端。

```python
# SSE Stream 格式
event: distraction
data: {"type": "idle_alert", "message": "已空闲5分钟...", "task_title": "写文档"}

event: distraction
data: {"type": "routine_check", "message": "检测到当前窗口与任务无关...", "window": "YouTube"}

event: task_completed
data: {"task_id": "xxx", "reward": "ASCII art..."}

event: heartbeat
data: {"timestamp": "2026-01-26T10:00:00"}
```

**事件类型**：
| 事件类型 | 触发时机 | 数据内容 |
|---------|---------|---------|
| `distraction` | IdleWatcher 检测到走神 | message, type, task_title |
| `task_completed` | 任务标记完成 | task_id, reward |
| `plan_updated` | 计划有变更 | date, tasks_count |
| `heartbeat` | 每 30s | timestamp |

**实现要点**：
- 使用 `asyncio.Queue` 作为事件队列
- IdleWatcher 的 `on_idle` 回调将事件推送到队列
- SSE 端点从队列读取并发送
- Heartbeat 保持连接活跃

---

## 四、走神检测系统集成

### 4.1 当前架构（CLI）

```
IdleWatcher (后台线程)
    ↓ on_idle callback
直接调用 FocusAgent.handle()
    ↓
print() 输出到终端
```

### 4.2 新架构（FastAPI）

```
IdleWatcher (后台线程)
    ↓ on_idle callback
调用 FocusAgent.handle() 获取响应
    ↓
检查是否需要静默 (<<SILENCE>>)
    ↓
推送到 event_queue
    ↓
SSE 端点读取并发送
    ↓
前端弹窗显示
```

### 4.3 实现细节

```python
# server.py 中的 on_idle 处理逻辑（伪代码）

def build_idle_handler(orchestrator, event_queue):
    def on_idle(payload):
        event_type = payload.get("type", "idle_alert")

        # 1. 构造消息（复用 main_mas.py 的逻辑）
        if event_type == "routine_check":
            message = f"[ROUTINE_CHECK] 当前窗口：{window}。当前任务：{task_title}"
        else:
            message = f"[IDLE_ALERT] 已空闲约 {idle_minutes} 分钟..."

        # 2. 调用 FocusAgent
        resp = orchestrator.focus_agent.handle(message)
        content = resp.get("content", "")

        # 3. 检查静默标记
        if "<<SILENCE>>" in content:
            return  # 不推送

        # 4. 推送到事件队列
        event_queue.put_nowait({
            "event": "distraction",
            "data": {
                "type": event_type,
                "message": content.replace("<<SILENCE>>", "").strip(),
                "task_title": task_title,
                "window": window
            }
        })

    return on_idle
```

### 4.4 为什么不用单独的走神接收接口？

最初考虑过 `POST /api/distraction` 接口，但分析后发现：

1. IdleWatcher 是**后台线程**，运行在同一进程内
2. 使用 HTTP 自调用会增加不必要的网络开销
3. 直接用函数回调 + 事件队列更简洁高效

因此采用：**回调函数 → 事件队列 → SSE 推送** 的架构。

---

## 五、Google Calendar OAuth 集成

### 5.1 ConnectOnion 现有流程分析

通过阅读 ConnectOnion 源码（`auth_commands.py`），`co auth google` 的完整流程如下：

```
┌─────────────────┐     ①检查 API Key     ┌─────────────────────┐
│  CLI 终端       │ ──────────────────→   │  OpenOnion 后端     │
│  co auth google │                        │  oo.openonion.ai    │
└─────────────────┘                        └──────────┬──────────┘
                                                      │
         ②GET /api/v1/oauth/google/init               │
         获取 auth_url                                │
         ←────────────────────────────────────────────┘
                    │
                    ▼
         ③webbrowser.open(auth_url)
         用户在浏览器完成 Google 授权
                    │
                    ▼
         ④轮询 GET /api/v1/oauth/google/status
         每 5 秒检查一次，最多等待 5 分钟
         直到 status.connected == True
                    │
                    ▼
         ⑤GET /api/v1/oauth/google/credentials
         获取 {access_token, refresh_token, expires_at, scopes, google_email}
                    │
                    ▼
         ⑥保存到 ~/.co/keys.env 和 ./.env
         GOOGLE_ACCESS_TOKEN=xxx
         GOOGLE_REFRESH_TOKEN=xxx
         GOOGLE_TOKEN_EXPIRES_AT=xxx
         GOOGLE_SCOPES=xxx
         GOOGLE_EMAIL=xxx
```

**关键发现**：
1. OAuth 流程通过 **OpenOnion 云端服务**代理，不是本地直接与 Google 交互
2. 需要 `OPENONION_API_KEY`（本应用采用开发者预置方式，用户无需自行获取）
3. Token 刷新也通过 OpenOnion 后端（`POST /api/v1/oauth/google/refresh`）

### 5.2 FastAPI 集成方案

**核心思路**：复用 ConnectOnion 的 OAuth 逻辑，通过 FastAPI 接口暴露给前端。

#### 5.2.1 检查授权状态

**`GET /api/auth/status`**

```python
# Response
{
    "google": {
        "connected": true,
        "email": "user@gmail.com",
        "scopes": "calendar",
        "expires_at": "2026-01-26T12:00:00Z"
    }
}

# 未连接时
{
    "google": {
        "connected": false,
        "message": "请点击「连接 Google 日历」完成授权"
    }
}
```

**实现要点**：
- `OPENONION_API_KEY` 已预置，无需检查（启动时若缺失则报错退出）
- 检查 `GOOGLE_ACCESS_TOKEN` 等 Google 凭证是否存在
- 检查 `GoogleCalendar()` 实例化是否成功
- 前端根据 `connected` 状态决定是否显示 OAuth 入口

#### 5.2.2 触发 Google OAuth

**`POST /api/auth/google`**

```python
# Response（立即返回）
{
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
    "poll_endpoint": "/api/auth/google/status",
    "timeout_seconds": 300
}
```

**实现要点**：
- 调用 OpenOnion API `GET /api/v1/oauth/google/init` 获取 auth_url
- 前端收到后用系统浏览器打开 auth_url
- 返回轮询端点供前端使用

#### 5.2.3 轮询 OAuth 状态

**`GET /api/auth/google/status`**

```python
# Response（授权中）
{
    "status": "pending",
    "message": "等待用户在浏览器中完成授权..."
}

# Response（授权成功）
{
    "status": "connected",
    "email": "user@gmail.com",
    "message": "Google 账号已连接"
}

# Response（授权失败/超时）
{
    "status": "failed",
    "message": "授权超时，请重试"
}
```

**实现要点**：
- 调用 OpenOnion API `GET /api/v1/oauth/google/status`
- 如果 `connected == True`：
  1. 调用 `GET /api/v1/oauth/google/credentials` 获取凭证
  2. 保存到 `.env` 文件
  3. 重新加载环境变量
  4. 热更新 `GoogleCalendar` 实例

### 5.3 OAuth 热更新流程

当用户完成 OAuth 授权后，需要热更新 Calendar 实例：

```python
# 伪代码
def on_google_auth_complete(credentials):
    # 1. 保存凭证到 .env
    save_google_credentials_to_env(credentials)

    # 2. 重新加载环境变量
    load_dotenv(override=True)

    # 3. 重新初始化 GoogleCalendar
    from connectonion import GoogleCalendar
    new_calendar = GoogleCalendar()  # 会读取新的环境变量

    # 4. 更新 PlanManager 的 calendar 引用
    app_state.orchestrator.plan_manager.calendar = new_calendar
    app_state.orchestrator.planner_agent.calendar = new_calendar
```

### 5.4 前端 OAuth 流程

```
┌─────────────┐     ①点击"连接Google"    ┌─────────────┐
│  Desktop UI │ ──────────────────────→  │   FastAPI   │
│  设置页面   │                          │   Server    │
└─────────────┘                          └──────┬──────┘
                                                │
       ②返回 auth_url                           │
       ←────────────────────────────────────────┘
            │
            ▼
       ③shell.openExternal(auth_url)
       用系统浏览器打开 Google 授权页
            │
            ▼
       ④轮询 /api/auth/google/status
       每 3 秒检查一次
            │
            ▼
       ⑤收到 status: "connected"
       显示"已连接"状态
```

### 5.5 OpenOnion API Key 处理

ConnectOnion 的 Google OAuth 依赖 `OPENONION_API_KEY`。

**采用方案：开发者预置 API Key**

由于本应用是面向终端用户的桌面产品，采用**开发者提供 API Key** 的模式：

```
┌─────────────────────────────────────────────────────────────┐
│                    应用分发包                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  backend/.env (预置)                                │   │
│  │  OPENONION_API_KEY=开发者的key                      │   │
│  │  GEMINI_API_KEY=开发者的key (可选)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          +                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  用户本地生成 (首次 Google OAuth 后)                │   │
│  │  GOOGLE_ACCESS_TOKEN=用户自己的token                │   │
│  │  GOOGLE_REFRESH_TOKEN=用户自己的token               │   │
│  │  GOOGLE_EMAIL=user@gmail.com                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**实现要点**：

1. **预置开发者 Key**
   - 应用打包时，`.env` 文件中预置 `OPENONION_API_KEY`
   - 用户无需运行任何命令行指令
   - LLM API Key（如 `GEMINI_API_KEY`）也可预置

2. **用户 Google 凭证隔离**
   - Google OAuth 获取的是**用户自己的 token**（访问用户自己的 Calendar）
   - 这些 token 保存在用户本地的 `.env` 文件中
   - 每个用户的 Google 账号相互独立

3. **安全考虑**
   - 开发者 API Key 仅用于调用 OpenOnion 的 OAuth 代理服务和 LLM 服务
   - 不会暴露用户的 Google 账号数据
   - 桌面应用本地运行，Key 不会被外部访问

4. **成本说明**
   - 所有用户的 LLM 调用费用由开发者承担
   - 建议后期考虑：用户自备 API Key 选项、使用量限制等

**简化后的用户流程**：

```
用户首次启动应用
    ↓
点击"连接 Google 日历"按钮
    ↓
浏览器打开 Google 授权页面
    ↓
用户授权
    ↓
完成，可以使用所有功能
```

用户**无需**：
- 运行 `co auth` 命令
- 获取自己的 OpenOnion 账号
- 配置任何 API Key

---

## 六、会话状态管理

### 6.1 单用户模式简化

由于是**桌面本地服务**，只有一个用户，会话管理可以大幅简化：

```python
# server.py

class AppState:
    """应用级单例状态"""
    orchestrator: OrchestratorAgent = None
    idle_watcher: IdleWatcher = None
    event_queue: asyncio.Queue = None

app_state = AppState()

@app.on_event("startup")
async def startup():
    # 初始化 Orchestrator
    app_state.orchestrator = OrchestratorAgent()

    # 初始化事件队列
    app_state.event_queue = asyncio.Queue()

    # 初始化 IdleWatcher
    app_state.idle_watcher = IdleWatcher(
        context_tool=app_state.orchestrator.focus_agent.context_tool,
        on_idle=build_idle_handler(app_state.orchestrator, app_state.event_queue),
        interval_seconds=30,
        idle_threshold_seconds=300,
        cooldown_seconds=600,
        focus_only=True,
        routine_check_seconds=300,
    )
    app_state.idle_watcher.start()

@app.on_event("shutdown")
async def shutdown():
    if app_state.idle_watcher:
        app_state.idle_watcher.stop()
```

### 6.2 locked_agent 状态

`OrchestratorAgent` 内部已经管理了 `locked_agent` 状态：
- 当某个 Agent 返回 `status: CONTINUE` 时，Orchestrator 会锁定到该 Agent
- 后续消息自动路由到被锁定的 Agent
- 直到 Agent 返回 `<<FINISHED>>` 或 `status: FINISHED`

**FastAPI 无需额外处理**，只需每次调用 `orchestrator.route(message)` 即可。

---

## 七、数据流与线程安全

### 7.1 线程模型

```
Main Thread (FastAPI/uvicorn)
    ├── 处理 HTTP 请求
    ├── 管理 SSE 连接
    └── asyncio 事件循环

Background Thread (IdleWatcher)
    ├── 每 30s 检测空闲时间
    ├── 每 5min 检测窗口相关性
    └── 触发 on_idle 回调

ThreadPoolExecutor (ParkingService)
    └── 异步执行 DuckDuckGo 搜索
```

### 7.2 线程安全考虑

| 场景 | 风险 | 解决方案 |
|-----|-----|---------|
| 同时读写任务 JSON | 文件损坏 | 使用 `threading.Lock` |
| 同时访问 Agent | 状态混乱 | Agent 调用本身是同步的，无并发 |
| 跨线程推送事件 | 竞态条件 | 使用 `asyncio.Queue`（线程安全） |

### 7.3 JSON 文件锁

```python
import threading

class PlanManagerWithLock(PlanManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._file_lock = threading.Lock()

    def _write_tasks(self, path, tasks):
        with self._file_lock:
            return super()._write_tasks(path, tasks)

    def _load_tasks(self, target_date, create_if_missing):
        with self._file_lock:
            return super()._load_tasks(target_date, create_if_missing)
```

---

## 八、错误处理

### 8.1 HTTP 错误码

| 状态码 | 场景 |
|-------|-----|
| 200 | 请求成功 |
| 400 | 参数错误（如日期格式错误） |
| 404 | 资源不存在（如任务 ID 不存在） |
| 500 | 服务器内部错误（Agent 调用失败等） |
| 503 | 服务不可用（如 Google Calendar 未授权） |

### 8.2 统一错误响应格式

```python
{
    "error": true,
    "code": "CALENDAR_NOT_AUTHORIZED",
    "message": "Google Calendar 未授权，请先完成 OAuth 认证",
    "detail": "..."  # 可选，调试信息
}
```

### 8.3 Agent 调用超时

Agent 调用可能因 LLM 响应慢而超时，建议：
- 设置请求超时为 60 秒
- 提供取消机制（前端可发送 abort 信号）
- 考虑未来支持 streaming response

---

## 九、文件结构建议

```
backend/
├── server.py              # FastAPI 主入口
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py        # POST /api/chat
│   │   ├── tasks.py       # GET/PATCH /api/tasks
│   │   ├── events.py      # SSE /api/events
│   │   ├── focus.py       # GET /api/focus/state
│   │   └── auth.py        # OAuth 相关
│   └── dependencies.py    # FastAPI 依赖注入
├── core/
│   ├── __init__.py
│   ├── state.py           # AppState 单例
│   ├── events.py          # 事件队列管理
│   └── oauth.py           # OAuth 辅助函数
├── agents/                # 现有 agents 目录不变
├── tools/                 # 现有 tools 目录不变
└── adhd_brain/            # 数据存储不变
```

---

## 十、开发优先级

### Phase 1: MVP（核心功能）

1. **服务启动**
   - FastAPI 应用初始化
   - OrchestratorAgent 单例
   - 基础健康检查 `GET /api/health`

2. **对话接口** `POST /api/chat`
   - 连接 Orchestrator
   - 返回标准响应格式

3. **任务接口** `GET /api/tasks`
   - 读取当日任务 JSON
   - 返回结构化数据

### Phase 2: 走神检测

4. **IdleWatcher 集成**
   - 后台线程启动
   - on_idle 回调实现

5. **SSE 推送** `GET /api/events`
   - 事件队列
   - 心跳保活

6. **专注状态** `GET /api/focus/state`
   - ContextTool 调用

### Phase 3: 完善功能

7. **任务更新** `PATCH /api/tasks/{id}`
   - 状态更新
   - 奖励生成

8. **Google OAuth**
   - 授权状态检查
   - OAuth 流程接口
   - 热更新 Calendar

### Phase 4: 优化

9. **错误处理完善**
10. **日志系统**
11. **配置管理**
12. **CORS 配置**（跨域支持）

---

## 十一、关键注意事项

### 11.1 ASCII Art 保留

Agent 返回的 cowsay ASCII art 必须完整保留：
```python
# 不要 strip 或格式化 ASCII art
response["ascii_art"] = raw_ascii_art
```

前端使用 `<pre>` 标签或等宽字体显示。

### 11.2 时区处理

- 后端使用本地时区（`datetime.datetime.now().astimezone()`）
- JSON 中存储的时间格式：`YYYY-MM-DD HH:MM`
- API 返回时附带时区信息

### 11.3 macOS 特性

- IdleWatcher 的 `get_idle_seconds()` 仅在 macOS 可用
- `get_active_window()` 使用 `osascript`
- 非 macOS 平台需要降级处理

### 11.4 环境变量加载

FastAPI 启动时需要加载环境变量：
```python
from dotenv import load_dotenv

# 加载 .env 文件（包含预置的开发者 Key 和用户的 Google 凭证）
load_dotenv()

# 启动时校验必要的 Key
if not os.getenv("OPENONION_API_KEY"):
    raise RuntimeError("OPENONION_API_KEY 未配置，请检查 .env 文件")
```

**环境变量分类**：

| 变量 | 来源 | 说明 |
|-----|-----|-----|
| `OPENONION_API_KEY` | 开发者预置 | 用于 OAuth 代理和 LLM 调用 |
| `GEMINI_API_KEY` | 开发者预置 | LLM 模型调用（可选） |
| `GOOGLE_ACCESS_TOKEN` | 用户 OAuth | 用户的 Calendar 访问令牌 |
| `GOOGLE_REFRESH_TOKEN` | 用户 OAuth | 用户的刷新令牌 |
| `GOOGLE_EMAIL` | 用户 OAuth | 用户的 Google 邮箱 |

---

## 十二、测试策略

### 12.1 单元测试

- API 路由测试（使用 FastAPI TestClient）
- PlanManager 方法测试
- OAuth 流程模拟测试

### 12.2 集成测试

- 完整对话流程测试
- 走神检测 → SSE 推送测试
- Google Calendar 同步测试（需要真实凭证）

### 12.3 手动测试

- 使用 Postman/curl 测试 API
- 使用浏览器测试 SSE 连接
- 使用前端原型测试完整流程

---

## 附录 A：ConnectOnion OAuth 相关代码引用

### A.1 GoogleCalendar 初始化检查

`connectonion/useful_tools/google_calendar.py:53-66`

```python
def __init__(self):
    scopes = os.getenv("GOOGLE_SCOPES", "")
    if "calendar" not in scopes:
        raise ValueError(
            "Missing 'calendar' scope.\n"
            f"Current scopes: {scopes}\n"
            "Please authorize Google Calendar access:\n"
            "  co auth google"
        )
```

### A.2 Token 刷新逻辑

`connectonion/useful_tools/google_calendar.py:112-168`

```python
def _refresh_via_backend(self, refresh_token: str) -> str:
    # 通过 OpenOnion 后端刷新 token
    response = httpx.post(
        f"{backend_url}/api/v1/oauth/google/refresh",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"refresh_token": refresh_token}
    )
    # ...更新环境变量和 .env 文件
```

### A.3 Google OAuth 流程

`connectonion/cli/commands/auth_commands.py:327-408`

```python
def handle_google_auth():
    # 1. 使用预置的 OPENONION_API_KEY
    # 2. GET /api/v1/oauth/google/init → auth_url
    # 3. webbrowser.open(auth_url)
    # 4. 轮询 GET /api/v1/oauth/google/status
    # 5. GET /api/v1/oauth/google/credentials
    # 6. 保存到 .env
```

---

## 附录 B：现有代码关键路径

| 功能 | 文件路径 |
|-----|---------|
| Orchestrator 路由 | `backend/agents/orchestrator.py` |
| PlannerAgent | `backend/agents/planner_agent.py` |
| FocusAgent | `backend/agents/focus_agent.py` |
| 任务管理 | `backend/tools/plan_tools_v2.py` |
| 走神检测 | `backend/tools/idle_watcher.py` |
| 专注状态 | `backend/tools/focus_tools.py` |
| 念头停车场 | `backend/tools/parking_tools.py` |
| 奖励系统 | `backend/tools/reward_tools.py` |
| CLI 入口 | `backend/main_mas.py` |
| 任务数据 | `backend/adhd_brain/daily_tasks_YYYY-MM-DD.json` |
