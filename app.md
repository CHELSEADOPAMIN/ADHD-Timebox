# ADHD Timebox 桌面应用转换方案

## 一、项目目标

将 ADHD Timebox 从 Web 应用（Next.js + Python FastAPI）转换为**桌面端本地服务（单用户）**应用，使用 Electron 作为桌面容器，Python 后端作为嵌入式服务。

---

## 二、当前架构分析

### 2.1 现有技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 16 + React 19 | App Router 架构 |
| 状态管理 | Zustand | 持久化到 localStorage |
| 认证 | Clerk | 云端认证服务 |
| 后端 | FastAPI + ConnectOnion | 多 Agent 系统 |
| 数据存储 | JSON 文件 | `backend/adhd_brain/users/{user_id}/` |

### 2.2 现有通信流程

```
浏览器 → Next.js API Routes (代理层) → FastAPI 后端 (localhost:8000)
         ↓
    Clerk 认证 + X-User-Id Header
```

### 2.3 需要改造的核心问题

1. **Clerk 认证**：云端服务，桌面应用无法使用
2. **多用户架构**：桌面应用只需单用户
3. **Next.js API 代理**：不需要代理层，可直接调用后端
4. **数据存储路径**：需要改为系统标准的应用数据目录

---

## 三、目标架构设计

### 3.1 推荐方案

```
┌─────────────────────────────────────────────────────────┐
│                    Electron 应用                         │
├─────────────────────────────────────────────────────────┤
│  主进程 (Main Process)                                   │
│  ├── 窗口管理 (BrowserWindow)                            │
│  ├── Python 进程管理 (spawn/kill)                        │
│  ├── 应用生命周期 (startup/shutdown)                     │
│  └── 数据目录管理 (app.getPath('userData'))              │
├─────────────────────────────────────────────────────────┤
│  渲染进程 (Renderer Process)                             │
│  ├── Next.js 静态导出 (next export)                      │
│  ├── React 组件 (现有组件，移除 Clerk)                    │
│  └── 直接调用后端 API (localhost:8000)                   │
├─────────────────────────────────────────────────────────┤
│  Python 后端 (子进程)                                    │
│  ├── FastAPI 服务 (PyInstaller 打包)                     │
│  ├── 单用户模式 (固定 default-user)                       │
│  └── 数据存储 (Electron userData 目录)                   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 方案选择理由

**前端选择：保留 Next.js + 静态导出**
- 现有 15+ 组件无需重写
- Clerk 仅在 5 个文件中使用，改动范围可控
- `next export` 可生成纯静态 HTML/JS，Electron 直接加载

**后端选择：PyInstaller 打包为独立可执行文件**
- 用户无需安装 Python
- 跨平台一致的运行时环境
- 单文件分发简化部署

**用户管理：固定 default-user**
- 保留现有的用户隔离架构代码
- 便于未来扩展多用户支持
- 改动最小（仅修改 1 个函数）

---

## 四、详细改造方案

### 4.1 目录结构变化

```
adhd-timebox/
├── electron/                      # 【新增】Electron 相关
│   ├── main.ts                    # 主进程入口
│   ├── preload.ts                 # 预加载脚本
│   └── python-manager.ts          # Python 进程管理
├── app/                           # 【修改】前端代码
│   ├── api/                       # 【删除】代理层不再需要
│   └── utils/
│       └── api.ts                 # 【修改】直接调用后端
├── backend/                       # 【修改】Python 后端
│   ├── api/dependencies.py        # 【修改】单用户模式
│   └── server.py                  # 【修改】支持外部数据目录
├── components/
│   ├── app-shell.tsx              # 【修改】移除 Clerk
│   └── auth-gate.tsx              # 【修改】简化为直接渲染
├── build/                         # 【新增】构建配置
│   └── pyinstaller/
│       └── adhd-backend.spec      # PyInstaller 配置
├── resources/                     # 【新增】打包资源
│   ├── icons/                     # 应用图标
│   └── backend/                   # 打包后的 Python 可执行文件
├── next.config.js                 # 【修改】启用静态导出
├── package.json                   # 【修改】添加 Electron 依赖
└── electron-builder.json          # 【新增】Electron 打包配置
```

### 4.2 文件改动清单

#### 需要新增的文件（5 个）

| 文件 | 作用 |
|------|------|
| `electron/main.ts` | Electron 主进程，管理窗口和 Python 子进程 |
| `electron/preload.ts` | IPC 通信桥接（可选，用于安全通信） |
| `electron/python-manager.ts` | Python 进程的启动、健康检查、关闭 |
| `build/pyinstaller/adhd-backend.spec` | PyInstaller 打包配置 |
| `electron-builder.json` | Electron 应用打包配置 |

#### 需要修改的文件（8 个）

| 文件 | 改动内容 |
|------|---------|
| `package.json` | 添加 electron、electron-builder 依赖和脚本 |
| `next.config.js` | 添加 `output: 'export'` 配置 |
| `app/layout.tsx` | 移除 ClerkProvider 和 Vercel Analytics |
| `components/app-shell.tsx` | 移除 useAuth、UserButton，使用固定 userId |
| `components/auth-gate.tsx` | 简化为直接返回 children |
| `app/utils/api.ts` | 基础 URL 改为 `http://localhost:8000`，移除 userId 参数 |
| `backend/api/dependencies.py` | `get_user_id()` 返回固定值 `"default-user"` |
| `backend/server.py` | 支持 `--data-dir` 参数，更新 CORS |

#### 需要删除的文件（11 个）

| 文件/目录 | 原因 |
|----------|------|
| `app/api/chat/route.ts` | 代理层不再需要 |
| `app/api/chat/stream/route.ts` | 代理层不再需要 |
| `app/api/tasks/route.ts` | 代理层不再需要 |
| `app/api/tasks/[taskId]/route.ts` | 代理层不再需要 |
| `app/api/parking/route.ts` | 代理层不再需要 |
| `app/api/focus/` 目录 | 代理层不再需要 |
| `app/api/calendar/` 目录 | 代理层不再需要 |
| `app/api/auth/` 目录 | Clerk 认证不再使用 |
| `middleware.ts` | Clerk 中间件不再需要 |

---

## 五、核心改造思路

### 5.1 Electron 主进程设计

**职责：**
1. 创建应用窗口
2. 启动 Python 后端子进程
3. 等待后端就绪后再显示窗口
4. 应用退出时优雅关闭 Python 进程

**关键流程：**
```
app.whenReady()
    ↓
启动 Python 后端 (spawn)
    ↓
轮询健康检查 (/api/health)
    ↓
后端就绪 → 创建 BrowserWindow
    ↓
加载静态页面 (out/index.html)
    ↓
用户关闭窗口 → SIGTERM 关闭 Python
```

**Python 进程管理要点：**
- 开发模式：运行 `backend/venv/bin/python -m uvicorn server:app`
- 生产模式：运行打包后的 `resources/backend/adhd-backend` 可执行文件
- 通过环境变量 `ADHD_DATA_DIR` 传递数据目录路径
- 健康检查：每 500ms 轮询 `/api/health`，最多等待 15 秒

### 5.2 前端认证移除

**当前 Clerk 使用位置：**

1. `app/layout.tsx` - ClerkProvider 包裹
2. `components/app-shell.tsx` - useAuth() 获取 userId、UserButton 组件
3. `components/planning-mode.tsx` - useAuth() 检查认证状态
4. `components/focus-mode.tsx` - useAuth() 获取 userId
5. `components/thought-parking-sheet.tsx` - useAuth() 获取 userId
6. `components/calendar-modal.tsx` - useAuth() 获取 userId

**改造策略：**
- 移除所有 `useAuth()` 调用
- 移除 `UserButton` 组件
- API 调用不再需要传 userId 参数（后端自动使用 default-user）
- `auth-gate.tsx` 简化为直接渲染子组件

### 5.3 API 调用改造

**改造前（通过代理）：**
```typescript
const res = await fetch("/api/chat", {
  headers: { "X-User-Id": userId },
  body: JSON.stringify({ message })
});
```

**改造后（直接调用后端）：**
```typescript
const BACKEND_URL = "http://localhost:8000";

const res = await fetch(`${BACKEND_URL}/api/chat`, {
  headers: { "X-User-Id": "default-user" },
  body: JSON.stringify({ message })
});
```

### 5.4 后端单用户模式

**改造 `backend/api/dependencies.py`：**

```python
def get_user_id(request: Request) -> str:
    # 桌面应用：固定使用 default-user
    return "default-user"
```

**改造 `backend/server.py`：**

```python
# 支持外部数据目录
import argparse

def create_app(data_dir: str = None) -> FastAPI:
    if data_dir:
        os.environ["ADHD_DATA_DIR"] = data_dir
    # ... 其余代码不变
```

**数据目录设计：**
- Windows: `%APPDATA%/ADHD-Timebox/data/`
- macOS: `~/Library/Application Support/ADHD-Timebox/data/`
- Linux: `~/.config/ADHD-Timebox/data/`

### 5.5 PyInstaller 打包

**打包配置要点：**
- 入口文件：`backend/server.py`
- 包含目录：`agents/`、`api/`、`core/`、`tools/`
- Hidden imports：`connectonion`、`litellm`、`uvicorn.logging`
- 输出：单个可执行文件（`--onefile`）

**注意事项：**
- ConnectOnion 可能有动态导入，需要手动添加 hiddenimports
- 测试时用 `--debug all` 排查缺失模块
- macOS 需要签名和公证才能正常分发

---

## 六、开发阶段划分

### 阶段 1：基础 Electron 框架（1-2 天）

**目标：** 让 Electron 能加载现有的 Next.js 开发服务器

**步骤：**
1. 安装 Electron 依赖
2. 创建基础 `electron/main.ts`
3. 配置 TypeScript 编译
4. 验证窗口可以加载 `localhost:3000`

### 阶段 2：移除 Clerk 认证（1 天）

**目标：** 前端完全脱离 Clerk，使用固定 userId

**步骤：**
1. 修改 `app/layout.tsx` 移除 ClerkProvider
2. 修改 5 个使用 useAuth() 的组件
3. 简化 `auth-gate.tsx`
4. 验证前端可以正常运行

### 阶段 3：API 直连改造（1 天）

**目标：** 前端绕过代理直接调用后端

**步骤：**
1. 修改 `app/utils/api.ts` 使用直接 URL
2. 修改后端 `dependencies.py` 返回固定用户
3. 更新 CORS 配置
4. 删除 `app/api/` 目录
5. 验证所有功能正常

### 阶段 4：Python 进程管理（2 天）

**目标：** Electron 自动启动和管理 Python 后端

**步骤：**
1. 创建 `electron/python-manager.ts`
2. 实现健康检查等待逻辑
3. 实现优雅关闭
4. 处理进程崩溃重启
5. 测试开发模式下的完整流程

### 阶段 5：静态导出配置（1 天）

**目标：** Next.js 导出为静态文件供 Electron 加载

**步骤：**
1. 修改 `next.config.js` 启用 `output: 'export'`
2. 解决可能的静态导出兼容问题
3. 验证 Electron 可以加载 `out/index.html`

### 阶段 6：PyInstaller 打包（2 天）

**目标：** Python 后端打包为独立可执行文件

**步骤：**
1. 创建 PyInstaller spec 文件
2. 处理 hidden imports
3. 测试单平台打包
4. 解决运行时依赖问题

### 阶段 7：Electron 打包分发（2 天）

**目标：** 完整应用打包为安装程序

**步骤：**
1. 配置 electron-builder
2. 集成 Python 可执行文件到 resources
3. 打包 macOS DMG / Windows NSIS / Linux AppImage
4. 测试完整安装流程

---

## 七、潜在风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| PyInstaller 缺失动态导入 | 运行时报错 | 使用 `--collect-all`，测试时用 `--debug` |
| 端口 8000 被占用 | 后端启动失败 | 实现动态端口分配 |
| macOS 签名公证 | 用户无法打开应用 | 获取 Apple 开发者证书 |
| Windows 杀毒误报 | 应用被拦截 | 代码签名 + 提交白名单 |
| Python 可执行文件体积大 | 安装包 200MB+ | 使用 UPX 压缩，排除无用模块 |

---

## 八、验证方案

### 开发阶段验证
```bash
# 1. 启动后端
cd backend && uvicorn server:app --reload

# 2. 启动前端
pnpm dev

# 3. 启动 Electron（开发模式）
pnpm electron:dev
```

### 生产打包验证
```bash
# 1. 打包 Python 后端
pnpm build:backend

# 2. 打包 Next.js 静态文件
pnpm build:next

# 3. 打包 Electron 应用
pnpm build:electron

# 4. 测试安装程序
open dist/ADHD-Timebox.dmg  # macOS
```

### 功能验证清单
- [ ] 应用启动时自动启动后端
- [ ] 任务创建、编辑、完成流程正常
- [ ] 思绪停车功能正常
- [ ] 专注模式计时正常
- [ ] 数据在应用重启后持久化
- [ ] 应用退出时后端进程正常关闭
- [ ] LLM API 调用正常（需网络）

---

## 九、关键文件路径

需要修改的核心文件：

| 文件 | 改动类型 |
|------|---------|
| `/Users/yangtiechui/Desktop/ADHD-Timebox/package.json` | 添加依赖和脚本 |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/next.config.js` | 静态导出配置 |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/app/layout.tsx` | 移除 Clerk |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/components/app-shell.tsx` | 移除 useAuth |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/components/auth-gate.tsx` | 简化组件 |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/app/utils/api.ts` | 直连后端 |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/backend/api/dependencies.py` | 单用户模式 |
| `/Users/yangtiechui/Desktop/ADHD-Timebox/backend/server.py` | 数据目录支持 |
