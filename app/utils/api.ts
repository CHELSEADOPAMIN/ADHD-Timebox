const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "http://localhost:8000";
const API_BASE = `${BACKEND_URL}/api`;

const extractErrorMessage = async (res: Response): Promise<string | null> => {
  try {
    const data = (await res.json()) as {
      message?: unknown;
      detail?: unknown;
      code?: unknown;
    };
    if (!data || typeof data !== "object") return null;
    const message =
      typeof data.message === "string" ? data.message.trim() : "";
    const detail = typeof data.detail === "string" ? data.detail.trim() : "";
    if (message && detail) return `${message} (${detail})`;
    if (message) return message;
    if (detail) return detail;
    return null;
  } catch {
    return null;
  }
};

export interface ChatResponse {
  content: string;
  status: string;
  agent: string;
  tasks_updated: boolean;
  ascii_art?: string | null;
}

export interface BackendTask {
  id: string;
  title: string;
  start?: string | null;
  end?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  type?: string;
  status: string;
  google_event_id?: string | null;
  sync_status?: "success" | "failed" | "pending" | null;
}

export interface RecommendationResponse {
  taskId: string;
  durationMinutes: number;
  reason: string;
  preferLowCognitiveLoad: boolean;
}

export interface ParkingResponse {
  content: string;
  status: string;
  agent: string;
}

interface TasksResponse {
  date: string;
  tasks: BackendTask[];
  summary?: {
    total: number;
    done: number;
    pending: number;
  };
}

export interface CalendarStatusResponse {
  connected: boolean;
  email?: string | null;
  expires_at?: string | null;
  message?: string | null;
  detail?: string | null;
  last_sync_time?: string | null;
  last_sync_summary?: {
    total: number;
    success: number;
    failed: number;
    pending: number;
  } | null;
}

export interface FocusStateResponse {
  status?: string;
  active_task?: {
    title?: string;
    start?: string | null;
    end?: string | null;
    remaining_minutes?: number | null;
    plan_date?: string | null;
  } | null;
  progress?: {
    done: number;
    total: number;
  };
  plan_path?: string | null;
  now?: string;
  message?: string;
  active_window?: string | null;
  idle_seconds?: number | null;
}

export const api = {
  chat: async (message: string): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) {
      const detail = await extractErrorMessage(res);
      const suffix = detail ? `: ${detail}` : "";
      throw new Error(`Chat failed${suffix}`);
    }
    return res.json();
  },

  getTasks: async (): Promise<BackendTask[]> => {
    const res = await fetch(`${API_BASE}/tasks`);
    if (!res.ok) {
      throw new Error("Failed to fetch tasks");
    }
    const data = (await res.json()) as TasksResponse;
    if (!data || !Array.isArray(data.tasks)) {
      return [];
    }
    return data.tasks;
  },

  updateTaskStatus: async (
    taskId: string,
    status: string
  ): Promise<void> => {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) {
      throw new Error("Failed to update task status");
    }
  },

  parkThought: async (
    message: string,
    thoughtType?: "search" | "memo" | "todo"
  ): Promise<ParkingResponse> => {
    const res = await fetch(`${API_BASE}/parking`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, thought_type: thoughtType }),
    });
    if (!res.ok) {
      throw new Error("Failed to park thought");
    }
    return res.json();
  },

  getCalendarStatus: async (): Promise<CalendarStatusResponse> => {
    const res = await fetch(`${API_BASE}/calendar/status`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error("Failed to fetch calendar status");
    }
    return res.json();
  },

  getFocusState: async (): Promise<FocusStateResponse> => {
    const res = await fetch(`${API_BASE}/focus/state`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error("Failed to fetch focus state");
    }
    return res.json();
  },

  syncCalendar: async (date?: string): Promise<any> => {
    const query = date ? `?date=${encodeURIComponent(date)}` : "";
    const res = await fetch(`${API_BASE}/calendar/sync${query}`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Calendar sync failed");
    }
    return res.json();
  },

  connectGoogleCalendar: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/calendar/connect`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Failed to start Google Calendar connection");
    }
    return res.json();
  },

  disconnectGoogleCalendar: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/calendar/disconnect`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Failed to disconnect Google Calendar");
    }
    return res.json();
  },

  downloadIcs: async (date?: string): Promise<Blob> => {
    const query = date ? `?date=${encodeURIComponent(date)}` : "";
    const res = await fetch(`${API_BASE}/calendar/ics${query}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error("Failed to download ICS");
    }
    return res.blob();
  },

  getGoogleAuthStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/google/status`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error("Failed to fetch Google auth status");
    }
    return res.json();
  },
};

// ============================================
// Session Management Types
// ============================================
 
export interface SessionState {
  status: "idle" | "running" | "paused" | "completed" | "abandoned";
  active_task?: {
    id?: string;
    title?: string;
    duration_minutes?: number;
    remaining_seconds?: number;
  } | null;
  duration_minutes: number;
  remaining_seconds: number;
  started_at?: string;
  paused_at?: string;
}
 
export interface SessionHistoryEntry {
  id: string;
  date: string;
  task_id?: string;
  task_title?: string;
  duration_minutes: number;
  actual_minutes: number;
  outcome: "completed" | "abandoned" | "interrupted";
  ended_at: string;
  reason?: string;
}
 
export interface SessionsResponse {
  current?: SessionState | null;
  history: SessionHistoryEntry[];
}
 
// Session Management Methods
export const sessionApi = {
  getSessions: async (): Promise<SessionsResponse> => {
    const res = await fetch(`${API_BASE}/sessions`);
    if (!res.ok) throw new Error("Failed to fetch sessions");
    return res.json();
  },
 
  startSession: async (
    taskId: string | null,
    durationMinutes: number
  ): Promise<{ success: boolean; session: SessionState }> => {
    const res = await fetch(`${API_BASE}/sessions/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        duration_minutes: durationMinutes,
      }),
    });
    if (!res.ok) throw new Error("Failed to start session");
    return res.json();
  },
 
  pauseSession: async (
    reason?: string
  ): Promise<{ success: boolean; session: SessionState }> => {
    const res = await fetch(`${API_BASE}/sessions/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error("Failed to pause session");
    return res.json();
  },
 
  resumeSession: async (): Promise<{ success: boolean; session: SessionState }> => {
    const res = await fetch(`${API_BASE}/sessions/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Failed to resume session");
    return res.json();
  },
 
  abandonSession: async (
    reason?: string
  ): Promise<{ success: boolean; history_entry: SessionHistoryEntry }> => {
    const res = await fetch(`${API_BASE}/sessions/abandon`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error("Failed to abandon session");
    return res.json();
  },
 
  completeSession: async (): Promise<{
    success: boolean;
    history_entry: SessionHistoryEntry;
  }> => {
    const res = await fetch(`${API_BASE}/sessions/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Failed to complete session");
    return res.json();
  },
};
