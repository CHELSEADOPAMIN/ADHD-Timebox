# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADHD Tymebox Agent is an AI-powered task management system for ADHD users, built on the "Tymeboxing" methodology. It uses a multi-agent architecture with planning, focus tracking, distraction management, and reward mechanisms.

**Tech Stack:**
- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS 4, Zustand (state), Radix UI
- Backend: FastAPI, Python 3.10+, ConnectOnion (agent framework), Gemini 2.5 Pro
- Package Manager: pnpm (frontend), pip (backend)

## Development Commands

### Frontend
```bash
pnpm install        # Install dependencies
pnpm dev            # Dev server at localhost:3000
pnpm build          # Production build
pnpm lint           # ESLint
```

### Backend
```bash
pip install -r requirements.txt                    # Install dependencies
python backend/server.py                           # FastAPI server at localhost:8000
# OR
uvicorn backend.server:app --reload --port 8000

python backend/main_mas.py                         # CLI mode (interactive)
```

### Running Locally
Run both servers simultaneously:
- Terminal 1: `python backend/server.py` (port 8000)
- Terminal 2: `pnpm dev` (port 3000)

## Architecture

### Multi-Agent System
```
User Input → OrchestratorAgent → Routes to:
                                  ├── PlannerAgent (task scheduling, tymeboxing)
                                  ├── FocusAgent (execution coaching, distraction handling)
                                  └── RewardAgent (completion celebrations)
```

**Key Design Patterns:**

1. **State Locking**: Agents call `acquire_lock()`/`release_lock()` for multi-turn conversations. Orchestrator force-routes to locked agent until released.

2. **System State Injection**: Every agent input includes `<System_State>` with current time, active task, today's plan. Prevents LLM context drift.

3. **Tools over Agents**: Specialized functions (ParkingService, IdleWatcher) are Tools, not separate Agents. Reduces token bloat and routing complexity.

### Backend Structure (`backend/`)
- `agents/orchestrator.py` - Central router with intent classification and state locking
- `agents/planner_agent.py` - Task scheduling (15/30/60 min tymeboxes), Google Calendar sync
- `agents/focus_agent.py` - Execution coach, distraction detection, micro-step suggestions
- `agents/reward_agent.py` - Celebration on task completion (ASCII art via cowsay)
- `tools/plan_tools_v2.py` - PlanManager: task CRUD, JSON persistence
- `tools/focus_tools.py` - ContextTool (active window, idle time), FocusToolkit
- `tools/parking_tools.py` - Thought parking (stores distracting ideas)
- `tools/idle_watcher.py` - Background thread for macOS idle detection

### Frontend Structure
- `components/app-shell.tsx` - Mode routing (planning/focusing/interrupted/resting)
- `lib/store.ts` - Zustand store with persist middleware
- `app/utils/api.ts` - Backend API client

### Data Storage
- Task files: `backend/adhd_brain/daily_tasks_YYYY-MM-DD.json`
- Memory: `backend/adhd_brain/long_term_memory/`
- Thought parking: `backend/adhd_brain/thought_parking/`

## API Endpoints

```
POST /api/chat              - Send message to OrchestratorAgent
GET  /api/tasks             - List today's tasks
PATCH /api/tasks/{id}       - Update task status
POST /api/recommend         - Get task recommendation
```

## Key Files for Understanding

1. `backend/agents/orchestrator.py` - Routing logic, state machine
2. `backend/tools/plan_tools_v2.py` - Task model and persistence
3. `backend/agents/prompts/planner_prompt.md` - Planning methodology
4. `lib/store.ts` - Frontend state management
5. `components/app-shell.tsx` - UI mode routing

## Environment Setup

Create `backend/.env`:
```
GEMINI_API_KEY=your_key
# OR
OPENAI_API_KEY=your_key
```

For Google Calendar sync: Place `credentials.json` in project root, authorize on first run.

## Platform Notes

- IdleWatcher only works on macOS (uses `ioreg` for idle detection)
- LLM model configured in agents (default: `co/gemini-2.5-pro`)
