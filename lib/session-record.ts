export type SessionStatus = "planning" | "focusing" | "archived";
export type SessionEndReason = "completed" | "stopped" | "interrupted";

export interface SessionMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  channel: "planning";
}

export interface SessionTaskSnapshot {
  id: string;
  title: string;
  description?: string;
  duration: number;
  status: string;
  startedAt?: Date;
  completedAt?: Date;
}

export interface SessionRecord {
  id: string;
  title: string;
  status: SessionStatus;
  startedAt: Date;
  endedAt?: Date;
  endReason?: SessionEndReason;
  taskSnapshot?: SessionTaskSnapshot;
  planningMessages: SessionMessage[];
}

const createId = (prefix: string) => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${prefix}-${Date.now()}`;
};

const createPlanningMessage = (
  content: string,
  timestamp: Date,
  role: SessionMessage["role"] = "user"
): SessionMessage => ({
  id: createId("message"),
  role,
  content,
  timestamp,
  channel: "planning",
});

const deriveTitle = (content: string) => {
  const trimmed = content.trim();
  if (!trimmed) {
    return "Planning session";
  }

  return trimmed.slice(0, 60);
};

export const createSessionFromMessage = (
  content: string,
  timestamp: Date,
  initialMessage?: SessionMessage
): SessionRecord => ({
  id: createId("session"),
  title: deriveTitle(content),
  status: "planning",
  startedAt: timestamp,
  planningMessages: [initialMessage ?? createPlanningMessage(content, timestamp)],
});

export const appendPlanningMessage = (
  session: SessionRecord,
  message: SessionMessage
): SessionRecord => ({
  ...session,
  planningMessages: [...session.planningMessages, message],
});

export const startFocusForSession = (
  session: SessionRecord,
  task: SessionTaskSnapshot
): SessionRecord => ({
  ...session,
  status: "focusing",
  taskSnapshot: {
    id: task.id,
    title: task.title,
    description: task.description,
    duration: task.duration,
    status: task.status,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
  },
});

export const archiveSession = (
  session: SessionRecord,
  endReason: SessionEndReason,
  endedAt: Date
): SessionRecord => ({
  ...session,
  status: "archived",
  endReason,
  endedAt,
});
