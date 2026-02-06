import { type BackendTask } from "@/app/utils/api";
import { type Task } from "@/lib/store";

const DEFAULT_TASK_DURATION_MINUTES = 30;

const parseTimeToDate = (time?: string | null): Date | null => {
  if (!time) return null;
  const trimmed = time.trim();
  if (/\d{4}-\d{2}-\d{2}/.test(trimmed)) {
    const iso = trimmed.replace(" ", "T");
    const parsed = new Date(iso);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed;
    }
  }
  const [hours, minutes, seconds] = trimmed.split(":").map((part) => Number(part));
  if (Number.isNaN(hours) || Number.isNaN(minutes)) {
    return null;
  }
  const date = new Date();
  date.setHours(hours, minutes, Number.isNaN(seconds) ? 0 : seconds, 0);
  return date;
};

const normalizeStatus = (status?: string): Task["status"] => {
  const normalized = (status || "").toLowerCase();
  if (["done", "completed", "complete"].includes(normalized)) {
    return "completed";
  }
  if (["in-progress", "in_progress", "active", "doing"].includes(normalized)) {
    return "in-progress";
  }
  if (normalized === "partial" || normalized === "stuck") {
    return normalized;
  }
  return "pending";
};

const getDurationMinutes = (task: BackendTask): number => {
  const start = parseTimeToDate(task.start_at || task.start);
  const end = parseTimeToDate(task.end_at || task.end);
  if (!start || !end) return DEFAULT_TASK_DURATION_MINUTES;
  const diffMinutes = Math.round((end.getTime() - start.getTime()) / 60000);
  return diffMinutes > 0 ? diffMinutes : DEFAULT_TASK_DURATION_MINUTES;
};

export const toStoreTask = (task: BackendTask): Task => {
  const startDate =
    parseTimeToDate(task.start_at || task.start || undefined) || undefined;
  const endDate =
    parseTimeToDate(task.end_at || task.end || undefined) || undefined;
  const status = normalizeStatus(task.status);

  return {
    id: task.id || crypto.randomUUID(),
    title: task.title?.trim() || "Untitled task",
    duration: getDurationMinutes(task),
    createdAt: startDate ?? new Date(),
    status,
    startedAt: status === "in-progress" ? startDate : undefined,
    completedAt: status === "completed" ? endDate : undefined,
    start: task.start ?? null,
    end: task.end ?? null,
    startAt: task.start_at ?? null,
    endAt: task.end_at ?? null,
    type: task.type ?? "work",
    googleEventId: task.google_event_id ?? null,
    syncStatus: task.sync_status ?? null,
  };
};
