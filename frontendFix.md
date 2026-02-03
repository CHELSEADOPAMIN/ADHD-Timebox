好的，我来给你一个完整的修改方案。

---

## ADHD Tymebox 前后端连接方案

### 一、目标

将前端 Next.js 应用与 Python 后端 (`localhost:8000`) 完全打通，实现：
1. 用户在前端聊天，消息发送给 Python Orchestrator Agent
2. Agent 的回复正确显示在前端
3. Agent 修改任务后，前端自动刷新任务列表

---

### 二、当前架构分析

#### 2.1 后端 API 端点 (已完成，无需修改)

| 端点 | 方法 | 功能 | 返回格式 |
|------|------|------|----------|
| `/api/chat` | POST | 与 Orchestrator 对话 | `{ content, status, agent, tasks_updated, ascii_art? }` |
| `/api/tasks` | GET | 获取今日任务列表 | `{ date, tasks: [...], summary }` |
| `/api/tasks/{id}` | PATCH | 更新任务状态 | `{ success, task, reward? }` |
| `/api/focus/state` | GET | 获取专注状态 | `{ active_window, idle_seconds, ... }` |
| `/api/events` | GET | SSE 实时事件流 | Server-Sent Events |

#### 2.2 前端当前问题

| 文件 | 问题 |
|------|------|
| `app/utils/api.ts` | `ChatResponse` 接口定义错误，字段名与后端不匹配 |
| `app/utils/api.ts` | `getTasks()` 返回格式错误，后端返回 `{ tasks: [...] }` 而非数组 |
| `app/utils/api.ts` | `bool` 应为 `boolean`（TypeScript 语法错误）|
| `components/planning-mode.tsx` | 使用 `useChat` 调用 Next.js 本地 API，绕过了 Python 后端 |
| `lib/store.ts` | 缺少 `setTasks()` 方法，无法批量设置从后端获取的任务 |
| `components/app-shell.tsx` | 应用启动时未从后端加载任务 |

---

### 三、修改方案

#### 3.1 修改 `app/utils/api.ts`

**目的**：修正接口定义，与 Python 后端返回格式对齐

**修改内容**：

1. **`ChatResponse` 接口**：
   - `response` → `content`
   - 新增 `agent`, `tasks_updated`, `ascii_art` 字段

2. **`BackendTask` 接口**：
   - 删除 `priority`, `estimatedMinutes`, `cognitiveLoad`（后端不返回）
   - 新增 `start`, `end`, `type`, `google_event_id`

3. **`RecommendationResponse` 接口**：
   - `bool` → `boolean`

4. **`getTasks()` 方法**：
   - 修改为解析 `{ date, tasks, summary }` 结构，只返回 `tasks` 数组

5. **删除 `getRecommendation()` 方法**：
   - 后端暂无此端点，先移除

---

#### 3.2 修改 `lib/store.ts`

**目的**：添加批量设置任务的方法

**修改内容**：

1. 在 `AppState` 接口中新增：
   ```
   setTasks: (tasks: Task[]) => void;
   ```

2. 在 store 实现中新增：
   ```
   setTasks: (tasks) => set({ tasks }),
   ```

---

#### 3.3 重写 `components/planning-mode.tsx`

**目的**：移除 AI SDK，改用直接调用 Python 后端

**修改内容**：

1. **删除**：
   - `import { useChat } from "@ai-sdk/react"`
   - `import { DefaultChatTransport } from "ai"`
   - 整个 `useChat` 调用

2. **新增**：
   - `import { api } from "@/app/utils/api"`
   - 本地状态 `isLoading` 管理加载状态

3. **改用 Zustand**：
   - 从 `useAppStore` 获取 `planningMessages`, `addPlanningMessage`, `setTasks`
   - 聊天记录持久化到 store 而非组件内部

4. **重写 `handleSubmit`**：
   ```
   1. 添加用户消息到 store
   2. 调用 api.chat(message)
   3. 添加 Agent 回复到 store
   4. 如果 tasks_updated === true，调用 api.getTasks() 刷新任务
   ```

5. **删除**：
   - 整个 Task 创建表单（`showTaskForm` 相关代码）
   - 因为任务创建由 Agent 通过对话完成，不需要手动表单

6. **调整消息渲染**：
   - 遍历 `planningMessages` 而非 `messages`
   - 直接使用 `message.content` 而非 `getMessageText()`

---

#### 3.4 修改 `components/app-shell.tsx`

**目的**：应用启动时从后端加载任务

**修改内容**：

1. **新增 import**：
   ```
   import { useEffect } from "react"
   import { api } from "@/app/utils/api"
   ```

2. **新增 useEffect**：
   - 组件挂载时调用 `api.getTasks()`
   - 将后端任务转换为前端 `Task` 类型
   - 调用 `setTasks()` 更新 store

3. **任务格式转换逻辑**：
   - `id` → `id`
   - `title` → `title`
   - `status: "done"/"completed"` → `status: "completed"`
   - `duration`: 根据 `start`/`end` 计算，或默认 30 分钟

---

#### 3.5 (可选) 删除或保留 `app/api/chat/` 目录

**说明**：

- `app/api/chat/planning/route.ts` 和 `app/api/chat/parking/route.ts` 是 Next.js 的本地 API 路由
- 修改后不再使用，可以：
  - **保留**：作为备用/演示
  - **删除**：清理无用代码

---

### 四、文件修改清单

| 文件 | 操作 | 优先级 |
|------|------|--------|
| `app/utils/api.ts` | 重写 | P0 |
| `lib/store.ts` | 小改（加 setTasks） | P0 |
| `components/planning-mode.tsx` | 重写 | P0 |
| `components/app-shell.tsx` | 小改（加初始化逻辑） | P1 |
| `app/hooks/useTaskPool.ts` | 检查/对齐 | P2 |
| `app/api/chat/*` | 可删除 | P3 |

---

### 五、测试验证步骤

1. **启动后端**：
   ```bash
   cd backend
   python server.py
   ```
   确认 `localhost:8000` 可访问

2. **启动前端**：
   ```bash
   pnpm dev
   ```

3. **测试聊天**：
   - 输入 "帮我安排下午2点写代码，1小时"
   - 预期：收到 Agent 回复，侧边栏任务列表自动更新

4. **测试任务加载**：
   - 刷新页面
   - 预期：之前创建的任务仍然显示在列表中

---

### 六、数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面 (Next.js)                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ PlanningMode │    │   Sidebar    │    │  AppShell    │       │
│  │  (聊天组件)   │    │  (任务列表)   │    │   (初始化)   │       │
│  └──────┬───────┘    └──────▲───────┘    └──────┬───────┘       │
│         │                   │                   │               │
│         ▼                   │                   │               │
│  ┌──────────────────────────┴───────────────────┘               │
│  │              Zustand Store (lib/store.ts)                    │
│  │   planningMessages[], tasks[], setTasks(), addTask()         │
│  └──────────────────────────┬───────────────────────────────────┘
│                             │                                   │
│  ┌──────────────────────────▼───────────────────────────────────┐
│  │              API Client (app/utils/api.ts)                   │
│  │       api.chat()  api.getTasks()  api.updateTaskStatus()     │
│  └──────────────────────────┬───────────────────────────────────┘
└─────────────────────────────┼───────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python 后端 (localhost:8000)                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ /api/chat    │───▶│ Orchestrator │───▶│ Planner/     │       │
│  │              │    │              │    │ Focus Agent  │       │
│  └──────────────┘    └──────────────┘    └──────┬───────┘       │
│                                                 │               │
│  ┌──────────────┐                               ▼               │
│  │ /api/tasks   │◀──────────────────── daily_tasks.json         │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

这就是完整的修改方案。当你准备好开始实施时，可以让我帮你逐个文件进行修改。