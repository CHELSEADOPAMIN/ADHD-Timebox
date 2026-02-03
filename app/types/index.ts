// State Definitions
export const FOCUS_STATES = {
  IDLE: "idle",
  RUNNING: "running",
  PAUSED: "paused",
  COMPLETED: "completed",
  ABANDONED: "abandoned",
} as const;

export type FocusState = (typeof FOCUS_STATES)[keyof typeof FOCUS_STATES];

export interface Task {
  id: string;
  title: string;
  priority: "urgent" | "medium" | "low";
  estimatedMinutes?: number;
  cognitiveLoad?: "low" | "medium" | "high";
  status?: string;
}

export interface SessionHistory {
  id: number;
  date: string;
  duration: number;
  outcome: "completed" | "abandoned" | "interrupted";
  taskId?: string;
}

export interface FocusStateData {
  status: FocusState;
  activeTaskId: string | null;
  durationMinutes: number;
  remainingSeconds: number;
  history: SessionHistory[];
}

export type FocusAction =
  | { type: "START"; payload: { taskId: string | null; duration: number } }
  | { type: "PAUSE" }
  | { type: "RESUME" }
  | { type: "TICK" }
  | { type: "ABANDON" }
  | { type: "RESET_COMPLETED" }
  | { type: "SET_DURATION"; payload: number };

// ============================================
// Orchestrator Types
// ============================================

// Event Types - 前端发送给 Orchestrator 的事件
export const ORCHESTRATOR_EVENTS = {
  APP_START: "APP_START",
  TYMEBOX_STARTED: "TYMEBOX_STARTED",
  TYMEBOX_ENDED: "TYMEBOX_ENDED",
  TYMEBOX_INTERRUPTED: "TYMEBOX_INTERRUPTED",
  REQUEST_NEW: "REQUEST_NEW",
} as const;

export type OrchestratorEventType =
  (typeof ORCHESTRATOR_EVENTS)[keyof typeof ORCHESTRATOR_EVENTS];

// Tymebox - 单个时间盒
export interface Tymebox {
  id: string;
  taskId: string;
  durationMinutes: number;
  startedAt?: string;
  endedAt?: string;
}

// Tymebox Outcome - 时间盒结果
export interface TymeboxOutcome {
  tymeboxId: string;
  taskId: string;
  durationMinutes: number;
  actualMinutes: number;
  outcome: "completed" | "abandoned" | "interrupted";
  endedAt: string;
}

// Decision Agent 推荐 - Agent 返回的推荐
export interface TymeboxRecommendation {
  taskId: string;
  durationMinutes: number;
  reason?: string;
  preferLowCognitiveLoad?: boolean;
}

// Orchestrator State - 编排器管理的状态
export interface OrchestratorState {
  // 当前活跃的时间盒
  activeTymebox: Tymebox | null;
  // Decision Agent 的推荐
  recommendation: TymeboxRecommendation | null;
  // 历史结果
  outcomes: TymeboxOutcome[];
  // 可用任务池
  tasks: Task[];
  // 是否正在加载推荐
  isLoadingRecommendation: boolean;
}

// Event Payload Types
export interface AppStartPayload {
  tasks: Task[];
}

export interface TymeboxStartedPayload {
  taskId: string;
  durationMinutes: number;
}

export interface TymeboxEndedPayload {
  taskId: string;
  durationMinutes: number;
  actualMinutes: number;
}

export interface TymeboxInterruptedPayload {
  taskId: string;
  durationMinutes: number;
  elapsedMinutes: number;
  reason?: string;
}

export interface RequestNewPayload {
  preferLowCognitiveLoad?: boolean;
}

// Orchestrator Event - 完整事件结构
export type OrchestratorEvent =
  | {
      event: typeof ORCHESTRATOR_EVENTS.APP_START;
      payload: AppStartPayload;
      state: OrchestratorState;
    }
  | {
      event: typeof ORCHESTRATOR_EVENTS.TYMEBOX_STARTED;
      payload: TymeboxStartedPayload;
      state: OrchestratorState;
    }
  | {
      event: typeof ORCHESTRATOR_EVENTS.TYMEBOX_ENDED;
      payload: TymeboxEndedPayload;
      state: OrchestratorState;
    }
  | {
      event: typeof ORCHESTRATOR_EVENTS.TYMEBOX_INTERRUPTED;
      payload: TymeboxInterruptedPayload;
      state: OrchestratorState;
    }
  | {
      event: typeof ORCHESTRATOR_EVENTS.REQUEST_NEW;
      payload: RequestNewPayload;
      state: OrchestratorState;
    };

// Orchestrator Output - 编排器返回给前端的新状态
export interface OrchestratorOutput {
  newState: OrchestratorState;
}

// Decision Agent Context - 传递给 Decision Agent 的上下文
export interface DecisionAgentContext {
  tasks: Task[];
  outcomes: TymeboxOutcome[];
  currentTime: string;
  preferLowCognitiveLoad?: boolean;
}
