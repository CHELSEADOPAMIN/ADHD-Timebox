"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/app/utils/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAppStore, type Task } from "@/lib/store";
import {
  Calendar,
  Download,
  RefreshCw,
  Link2,
  Unlink,
  X,
  Play,
  CheckCircle2,
} from "lucide-react";

const DAY_START_HOUR = 8;
const DAY_END_HOUR = 22;
const HOUR_HEIGHT = 80;

const formatDateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const extractDateKey = (value?: string | null) => {
  if (!value) return null;
  const match = value.match(/(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
};

const extractMinutes = (value?: string | null) => {
  if (!value) return null;
  const trimmed = value.trim();
  const timePart = trimmed.includes("T")
    ? trimmed.split("T")[1]
    : trimmed.includes(" ")
    ? trimmed.split(" ")[1]
    : trimmed;
  const match = timePart.match(/(\d{1,2}):(\d{2})/);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return null;
  return hours * 60 + minutes;
};

const formatTimeLabel = (minutes: number) => {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
};

const statusLabel = (status?: string | null) => {
  const normalized = (status || "").toLowerCase();
  if (normalized === "completed") return "Completed";
  if (normalized === "in-progress") return "In progress";
  if (normalized === "pooled") return "Pooled";
  return "Pending";
};

const typeStyles: Record<string, string> = {
  work: "bg-primary/15 border-primary/40 text-foreground",
  break: "bg-emerald-500/15 border-emerald-500/40 text-foreground",
  rest: "bg-emerald-500/15 border-emerald-500/40 text-foreground",
  buffer: "bg-amber-400/20 border-amber-400/50 text-foreground",
  life: "bg-sky-500/15 border-sky-500/40 text-foreground",
};

const defaultTaskStyle = "bg-muted/40 border-border text-foreground";

const getWeekStart = (date: Date) => {
  const start = new Date(date);
  const day = start.getDay();
  const diff = (day + 6) % 7; // Monday start
  start.setDate(start.getDate() - diff);
  start.setHours(0, 0, 0, 0);
  return start;
};

export function CalendarModal() {
  const {
    calendarModalOpen,
    setCalendarModalOpen,
    calendarView,
    setCalendarView,
    tasks,
    currentTask,
    updateTask,
    setCurrentTask,
    setTimeRemaining,
    setIsTimerRunning,
    setUserState,
    googleCalendarConnected,
    setGoogleCalendarConnected,
    lastSyncTime,
    setLastSyncTime,
  } = useAppStore();

  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!calendarModalOpen) return;
    setSelectedDate(new Date());
    setSelectedTaskId(null);
  }, [calendarModalOpen]);

  useEffect(() => {
    if (!calendarModalOpen) return;
    const fetchStatus = async () => {
      try {
        const status = await api.getCalendarStatus();
        setGoogleCalendarConnected(Boolean(status.connected));
        setLastSyncTime(status.last_sync_time ?? null);
      } catch (error) {
        console.error("Failed to load calendar status", error);
      }
    };
    fetchStatus();
  }, [calendarModalOpen, setGoogleCalendarConnected, setLastSyncTime]);

  useEffect(() => {
    if (!calendarModalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setCalendarModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [calendarModalOpen, setCalendarModalOpen]);

  const selectedDateKey = formatDateKey(selectedDate);
  const dayStartMinutes = DAY_START_HOUR * 60;
  const dayEndMinutes = DAY_END_HOUR * 60;
  const totalMinutes = dayEndMinutes - dayStartMinutes;
  const gridHeight = totalMinutes * (HOUR_HEIGHT / 60);

  const allCalendarTasks = useMemo(() => {
    return tasks
      .filter((task) => task.start || task.end || task.startAt || task.endAt)
      .map((task) => {
        const dateKey =
          extractDateKey(task.startAt) ||
          extractDateKey(task.endAt) ||
          extractDateKey(task.start) ||
          extractDateKey(task.end) ||
          selectedDateKey;
        const startMinutes =
          extractMinutes(task.startAt) || extractMinutes(task.start);
        const endMinutes = extractMinutes(task.endAt) || extractMinutes(task.end);
        return {
          task,
          dateKey,
          startMinutes,
          endMinutes,
        };
      })
      .filter(
        (entry) =>
          entry.startMinutes !== null &&
          entry.endMinutes !== null &&
          entry.endMinutes > entry.startMinutes
      );
  }, [tasks, selectedDateKey]);

  const tasksByDay = useMemo(() => {
    const map = new Map<string, typeof allCalendarTasks>();
    allCalendarTasks.forEach((entry) => {
      const list = map.get(entry.dateKey) ?? [];
      list.push(entry);
      map.set(entry.dateKey, list);
    });
    return map;
  }, [allCalendarTasks]);

  const weekDays = useMemo(() => {
    const start = getWeekStart(selectedDate);
    return Array.from({ length: 7 }, (_, idx) => {
      const date = new Date(start);
      date.setDate(start.getDate() + idx);
      return date;
    });
  }, [selectedDate]);

  const renderTasksForDay = (dateKey: string, columnIndex = 0) => {
    const entries = (tasksByDay.get(dateKey) ?? [])
      .filter((entry) => {
        if (entry.endMinutes === null || entry.startMinutes === null) return false;
        return (
          entry.endMinutes > dayStartMinutes &&
          entry.startMinutes < dayEndMinutes
        );
      })
      .sort((a, b) => (a.startMinutes ?? 0) - (b.startMinutes ?? 0));

    if (!entries.length) return null;

    return entries.map((entry) => {
      const start = Math.max(entry.startMinutes ?? 0, dayStartMinutes);
      const end = Math.min(entry.endMinutes ?? 0, dayEndMinutes);
      const top = ((start - dayStartMinutes) / 60) * HOUR_HEIGHT;
      const height = Math.max(((end - start) / 60) * HOUR_HEIGHT, 28);
      const isActive =
        currentTask?.id === entry.task.id ||
        entry.task.status === "in-progress";
      const isCompleted = entry.task.status === "completed";
      const styleKey = entry.task.type || "default";
      const colorClass = typeStyles[styleKey] ?? defaultTaskStyle;

      return (
        <button
          key={`${entry.task.id}-${columnIndex}`}
          type="button"
          onClick={() => setSelectedTaskId(entry.task.id)}
          className={cn(
            "absolute left-2 right-2 flex flex-col gap-1 rounded-lg border px-3 py-2 text-left shadow-sm transition",
            colorClass,
            isCompleted && "opacity-60 line-through",
            isActive && "ring-2 ring-primary/70 animate-pulse"
          )}
          style={{ top, height }}
        >
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            {entry.task.type ?? "task"}
          </span>
          <span className="truncate text-sm font-medium">{entry.task.title}</span>
          <span className="text-xs text-muted-foreground">
            {formatTimeLabel(start)} - {formatTimeLabel(end)}
          </span>
        </button>
      );
    });
  };

  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? null;

  const handleDownloadIcs = async () => {
    const dateKey = formatDateKey(selectedDate);
    try {
      const blob = await api.downloadIcs(dateKey);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `timebox_${dateKey}.ics`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download ICS", error);
      setStatusMessage("Download failed. Please try again.");
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    setStatusMessage(null);
    try {
      const dateKey = formatDateKey(selectedDate);
      const result = await api.syncCalendar(dateKey);
      setLastSyncTime(result.last_sync_time ?? new Date().toISOString());
      setStatusMessage("Sync complete.");
    } catch (error) {
      console.error("Calendar sync failed", error);
      setStatusMessage("Sync failed. Please try again.");
    } finally {
      setIsSyncing(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    setStatusMessage(null);
    try {
      const response = await api.connectGoogleCalendar();
      const authUrl = response.auth_url as string | undefined;
      if (authUrl) {
        window.open(authUrl, "_blank", "noopener,noreferrer");
      }

      const deadline = Date.now() + 4 * 60 * 1000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const pollBody = await api.getGoogleAuthStatus();
        if (pollBody?.status === "connected") {
          setGoogleCalendarConnected(true);
          setStatusMessage("Google Calendar connected.");
          return;
        }
        if (pollBody?.status === "failed") {
          setStatusMessage(pollBody?.message || "Connection failed.");
          return;
        }
      }
      setStatusMessage("Still waiting on authorization.");
    } catch (error) {
      console.error("Failed to connect Google Calendar", error);
      setStatusMessage("Connection failed. Please try again.");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await api.disconnectGoogleCalendar();
      setGoogleCalendarConnected(false);
      setStatusMessage("Google Calendar disconnected.");
    } catch (error) {
      console.error("Failed to disconnect Google Calendar", error);
      setStatusMessage("Disconnect failed.");
    }
  };

  const handleStartTask = (task: Task) => {
    const startedAt = new Date();
    updateTask(task.id, { status: "in-progress", startedAt });
    setCurrentTask({ ...task, status: "in-progress", startedAt });
    setTimeRemaining(task.duration * 60);
    setIsTimerRunning(true);
    setUserState("focusing");
  };

  const handleMarkComplete = async (task: Task) => {
    updateTask(task.id, { status: "completed", completedAt: new Date() });
    if (currentTask?.id === task.id) {
      setCurrentTask({ ...task, status: "completed", completedAt: new Date() });
      setIsTimerRunning(false);
      setTimeRemaining(0);
      setUserState("resting");
    }
    try {
      await api.updateTaskStatus(task.id, "completed");
    } catch (error) {
      console.error("Failed to update task status", error);
    }
  };

  if (!calendarModalOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm"
      onClick={() => setCalendarModalOpen(false)}
    >
      <div
        className="mx-4 flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Calendar className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Calendar view</p>
              <h2 className="text-lg font-semibold text-foreground">
                {selectedDate.toLocaleDateString(undefined, {
                  weekday: "long",
                  month: "short",
                  day: "numeric",
                })}
              </h2>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={calendarView === "day" ? "default" : "outline"}
              size="sm"
              onClick={() => setCalendarView("day")}
            >
              Day
            </Button>
            <Button
              variant={calendarView === "week" ? "default" : "outline"}
              size="sm"
              onClick={() => setCalendarView("week")}
            >
              Week
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCalendarModalOpen(false)}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </Button>
          </div>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 overflow-hidden">
            <div className="w-16 shrink-0 border-r border-border bg-muted/20">
              <div className="h-10 border-b border-border" />
              <div className="relative" style={{ height: gridHeight }}>
                {Array.from(
                  { length: DAY_END_HOUR - DAY_START_HOUR + 1 },
                  (_, idx) => {
                    const hour = DAY_START_HOUR + idx;
                    const top = idx * HOUR_HEIGHT;
                    return (
                      <div
                        key={hour}
                        className="absolute left-0 right-0 flex items-start justify-center text-xs text-muted-foreground"
                        style={{ top: top - 6 }}
                      >
                        {String(hour).padStart(2, "0")}:00
                      </div>
                    );
                  }
                )}
              </div>
            </div>

            <div className="flex-1 overflow-auto bg-background">
              {calendarView === "day" ? (
                <div className="min-w-[480px] border-b border-border">
                  <div className="h-10 border-b border-border bg-muted/20 px-4 text-xs uppercase tracking-wider text-muted-foreground flex items-center">
                    Schedule
                  </div>
                  <div className="relative" style={{ height: gridHeight }}>
                    {Array.from(
                      { length: DAY_END_HOUR - DAY_START_HOUR },
                      (_, idx) => {
                        const top = idx * HOUR_HEIGHT;
                        return (
                          <div
                            key={idx}
                            className="absolute left-0 right-0 border-t border-border/50"
                            style={{ top }}
                          />
                        );
                      }
                    )}
                    {renderTasksForDay(selectedDateKey)}
                  </div>
                </div>
              ) : (
                <div className="min-w-[720px]">
                  <div className="grid grid-cols-7 border-b border-border bg-muted/20 text-xs uppercase tracking-wider text-muted-foreground">
                    {weekDays.map((day) => (
                      <div
                        key={day.toISOString()}
                        className={cn(
                          "px-3 py-2 text-center",
                          formatDateKey(day) === selectedDateKey &&
                            "text-primary"
                        )}
                      >
                        {day.toLocaleDateString(undefined, {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })}
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-7">
                    {weekDays.map((day, index) => {
                      const dateKey = formatDateKey(day);
                      return (
                        <div
                          key={day.toISOString()}
                          className="relative border-r border-border last:border-r-0"
                          style={{ height: gridHeight }}
                        >
                          {Array.from(
                            { length: DAY_END_HOUR - DAY_START_HOUR },
                            (_, idx) => {
                              const top = idx * HOUR_HEIGHT;
                              return (
                                <div
                                  key={idx}
                                  className="absolute left-0 right-0 border-t border-border/50"
                                  style={{ top }}
                                />
                              );
                            }
                          )}
                          {renderTasksForDay(dateKey, index)}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {selectedTask && (
            <div className="border-t border-border bg-muted/10 px-6 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {selectedTask.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {statusLabel(selectedTask.status)} ·{" "}
                    {selectedTask.type ?? "task"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleStartTask(selectedTask)}
                  >
                    <Play className="h-3 w-3" />
                    Start
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleMarkComplete(selectedTask)}
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    Mark done
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelectedTaskId(null)}
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>
          )}

          <div className="border-t border-border bg-card px-6 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={handleDownloadIcs}>
                  <Download className="h-4 w-4" />
                  Download ICS
                </Button>
                <Button
                  variant="outline"
                  onClick={handleSync}
                  disabled={isSyncing || !googleCalendarConnected}
                >
                  <RefreshCw
                    className={cn(
                      "h-4 w-4",
                      isSyncing && "animate-spin"
                    )}
                  />
                  {isSyncing ? "Syncing..." : "Sync now"}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      googleCalendarConnected ? "bg-emerald-500" : "bg-muted-foreground/40"
                    )}
                  />
                  <span>
                    {googleCalendarConnected
                      ? "Google Calendar connected"
                      : "Google Calendar not connected"}
                  </span>
                </div>
                {lastSyncTime && (
                  <span>
                    Last sync{" "}
                    {new Date(lastSyncTime).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                )}
                <div className="flex items-center gap-2">
                  {googleCalendarConnected ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleDisconnect}
                    >
                      <Unlink className="h-3 w-3" />
                      Disconnect
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleConnect}
                      disabled={isConnecting}
                    >
                      <Link2 className="h-3 w-3" />
                      {isConnecting ? "Connecting..." : "Connect"}
                    </Button>
                  )}
                </div>
              </div>
            </div>
            {statusMessage && (
              <p className="mt-2 text-xs text-muted-foreground">
                {statusMessage}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
