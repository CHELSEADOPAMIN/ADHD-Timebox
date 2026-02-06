"use client";

import React, { useState, useRef } from "react";

import { useAppStore, type Task } from "@/lib/store";
import { cn } from "@/lib/utils";
import {
  Clock,
  Circle,
  CheckCircle2,
  Calendar,
  Play,
  X,
  ChevronRight,
  ListTodo,
  Heart,
} from "lucide-react";
import { Button } from "@/components/ui/button";

// Mock data for tasks
const mockTasks: Task[] = [
  {
    id: "1",
    title: "Review design feedback",
    duration: 15,
    status: "in-progress",
    createdAt: new Date(),
    startedAt: new Date(),
  },
  {
    id: "2",
    title: "Reply to Sarah's email",
    duration: 10,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "3",
    title: "Update project notes",
    duration: 20,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "4",
    title: "Quick break + stretch",
    duration: 5,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "5",
    title: "Check Slack messages",
    duration: 10,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "6",
    title: "Review pull requests",
    duration: 25,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "7",
    title: "Write meeting notes",
    duration: 15,
    status: "pending",
    createdAt: new Date(),
  },
  {
    id: "8",
    title: "Update documentation",
    duration: 30,
    status: "pending",
    createdAt: new Date(),
  },
];


type SectionId = "tasks" | "calendar" | "status";

function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

function CollapsibleSection({
  id,
  title,
  icon: Icon,
  isExpanded,
  onToggle,
  isMuted,
  children,
  badge,
}: {
  id: SectionId;
  title: string;
  icon: React.ElementType;
  isExpanded: boolean;
  onToggle: () => void;
  isMuted: boolean;
  children: React.ReactNode;
  badge?: string | number;
}) {
  return (
    <div className="border-b border-border/50 last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors",
          "hover:bg-muted/30",
          isExpanded && "bg-muted/20"
        )}
      >
        <ChevronRight
          className={cn(
            "h-4 w-4 shrink-0 transition-transform duration-200",
            isMuted ? "text-muted-foreground/50" : "text-muted-foreground",
            isExpanded && "rotate-90"
          )}
        />
        <Icon
          className={cn(
            "h-4 w-4 shrink-0",
            isMuted ? "text-muted-foreground/50" : "text-muted-foreground"
          )}
        />
        <span
          className={cn(
            "flex-1 text-xs font-medium uppercase tracking-wider",
            isMuted ? "text-muted-foreground/50" : "text-muted-foreground"
          )}
        >
          {title}
        </span>
        {badge !== undefined && (
          <span
            className={cn(
              "rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium",
              isMuted ? "text-muted-foreground/50" : "text-primary"
            )}
          >
            {badge}
          </span>
        )}
      </button>
      <div
        className={cn(
          "grid transition-all duration-200 ease-in-out",
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="max-h-48 overflow-y-auto px-4 pb-3">{children}</div>
        </div>
      </div>
    </div>
  );
}

function TaskItem({
  task,
  isActive,
  isMuted,
  isSelected,
  onSelect,
  onStart,
  onDismiss,
}: {
  task: Task;
  isActive: boolean;
  isMuted: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onStart: () => void;
  onDismiss: () => void;
}) {
  const getStatusIcon = () => {
    if (task.status === "completed") {
      return <CheckCircle2 className="h-4 w-4 text-safe" />;
    }
    if (isActive || task.status === "in-progress") {
      return <Circle className="h-4 w-4 fill-primary/20 text-primary" />;
    }
    return <Circle className="h-4 w-4 text-muted-foreground/50" />;
  };

  const isClickable = !isMuted && (task.status === "pending" || task.status === "pooled");

  return (
    <div className="relative">
      <button
        type="button"
        onClick={isClickable ? onSelect : undefined}
        disabled={!isClickable}
        className={cn(
          "flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-all",
          (isActive || task.status === "in-progress") &&
            !isMuted &&
            "bg-primary/5",
          isSelected && "bg-primary/10 ring-1 ring-primary/30",
          isMuted && "opacity-50",
          isClickable && "cursor-pointer hover:bg-muted/50"
        )}
      >
        <div className="mt-0.5 shrink-0">{getStatusIcon()}</div>
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "truncate text-sm",
              (isActive || task.status === "in-progress") && !isMuted
                ? "font-medium text-foreground"
                : "text-muted-foreground"
            )}
          >
            {task.title}
          </p>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground/70">
            <Clock className="h-3 w-3" />
            <span>{formatDuration(task.duration)}</span>
          </div>
        </div>
      </button>

      {/* Action buttons when selected */}
      {isSelected && !isMuted && (
        <div className="mt-2 flex items-center gap-2 px-3 pb-2 animate-in fade-in slide-in-from-top-1 duration-200">
          <Button
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onStart();
            }}
            className="h-7 flex-1 gap-1.5 text-xs"
          >
            <Play className="h-3 w-3" />
            Start
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
            className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
            Not now
          </Button>
        </div>
      )}
    </div>
  );
}


export function Sidebar() {
  const {
    userState,
    tasks,
    currentTask,
    setCurrentTask,
    updateTask,
    setUserState,
    setTimeRemaining,
    setIsTimerRunning,
    setCalendarModalOpen,
  } = useAppStore();

  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<SectionId>>(
    new Set(["tasks"])
  );
  const [isHovered, setIsHovered] = useState(false);

  // Remember last expanded sections (so hover can restore)
  const lastExpandedRef = useRef<Set<SectionId>>(new Set(["tasks"]));

  // Visibility rules based on state
  const isHidden = userState === "interrupted";
  const isMuted = userState === "focusing";
  const isPartiallyVisible = userState === "resting";

  // Hover-only control: enter expands (restore), leave collapses
  const handleMouseEnter = () => {
    setIsHovered(true);

    const toRestore =
      lastExpandedRef.current.size > 0
        ? new Set(lastExpandedRef.current)
        : new Set<SectionId>(["tasks"]);

    setExpandedSections(toRestore);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);

    // Persist what was open, so next hover restores it
    if (expandedSections.size > 0) {
      lastExpandedRef.current = new Set(expandedSections);
    }

    // Collapse immediately on leave
    setExpandedSections(new Set());
    setSelectedTaskId(null);
  };

  // Don't render at all when hidden
  if (isHidden) {
    return null;
  }

  const visibleTasks = tasks.filter(
    (t) => t.status !== "completed" || t.id === currentTask?.id
  );

  const formatTime = (time?: string | null) => {
    if (!time) return null;
    const trimmed = time.trim();
    const part = trimmed.includes("T")
      ? trimmed.split("T")[1]
      : trimmed.includes(" ")
      ? trimmed.split(" ")[1]
      : trimmed;
    return part.slice(0, 5);
  };

  const calendarPreviewEvents = tasks
    .filter((task) => task.start || task.startAt)
    .map((task) => ({
      id: task.id,
      title: task.title,
      time: formatTime(task.startAt || task.start) || "--:--",
      duration: task.duration,
    }))
    .sort((a, b) => a.time.localeCompare(b.time));

  // Toggle section expansion (only meaningful while expanded)
  const toggleSection = (sectionId: SectionId) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

  // Handle starting a task
  const handleStartTask = (task: Task) => {
    const startedAt = new Date();
    updateTask(task.id, { status: "in-progress", startedAt });
    setCurrentTask({
      ...task,
      status: "in-progress",
      startedAt,
    });
    setTimeRemaining(task.duration * 60);
    setIsTimerRunning(true);
    setUserState("focusing");
    setSelectedTaskId(null);
  };

  // Handle dismissing selection
  const handleDismiss = () => {
    setSelectedTaskId(null);
  };

  // Gentle contextual messages based on state
  const getContextMessage = () => {
    if (isMuted) {
      return "Everything is saved here. Focus on what's in front of you.";
    }
    if (isPartiallyVisible) {
      return "When you're ready, your tasks will be here. No rush.";
    }
    if (currentTask) {
      return "You only need to focus on the current task.";
    }
    if (selectedTaskId) {
      return "Ready when you are. No pressure.";
    }
    return "Small steps. You've got this.";
  };

  // ✅ Collapsed state is controlled ONLY by hover
  const isCollapsed = false; // !isHovered;

  return (
    <aside
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "fixed left-0 top-14 z-30 hidden h-[calc(100vh-3.5rem)] border-r border-border bg-sidebar lg:flex lg:flex-col",
        "transition-all duration-300 ease-in-out",
        isCollapsed ? "w-16" : "w-72",
        isMuted && "pointer-events-none opacity-60",
        isPartiallyVisible && "opacity-80"
      )}
    >
      {/* Collapsed state - just icons (NO CLICK TO WAKE) */}
      {isCollapsed && (
        <div className="flex flex-1 flex-col items-center gap-2 py-4">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
            title="Current / Tasks"
          >
            <ListTodo className="h-5 w-5" />
          </div>
          <button
            type="button"
            onClick={() => setCalendarModalOpen(true)}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
            title="Open calendar"
          >
            <Calendar className="h-5 w-5" />
          </button>
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
            title="Status"
          >
            <Heart className="h-5 w-5" />
          </div>
        </div>
      )}

      {/* Expanded state - full content */}
      {!isCollapsed && (
        <>
          {/* Scrollable sections area */}
          <div className="flex-1 overflow-y-auto">
            {/* Current / Tasks Section */}
            <CollapsibleSection
              id="tasks"
              title="Current / Tasks"
              icon={ListTodo}
              isExpanded={expandedSections.has("tasks")}
              onToggle={() => toggleSection("tasks")}
              isMuted={isMuted}
              badge={visibleTasks.length}
            >
              {visibleTasks.length > 0 ? (
                <div className="space-y-1">
                  {visibleTasks.map((task) => (
                    <TaskItem
                      key={task.id}
                      task={task}
                      isActive={currentTask?.id === task.id}
                      isMuted={isMuted}
                      isSelected={selectedTaskId === task.id}
                      onSelect={() => handleStartTask(task)}
                      onStart={() => handleStartTask(task)}
                      onDismiss={handleDismiss}
                    />
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center">
                  <p className="text-sm text-muted-foreground/60">
                    No tasks planned
                  </p>
                </div>
              )}
            </CollapsibleSection>

            {/* Calendar Preview Section */}
            <CollapsibleSection
              id="calendar"
              title="Calendar Preview"
              icon={Calendar}
              isExpanded={expandedSections.has("calendar")}
              onToggle={() => toggleSection("calendar")}
              isMuted={isMuted}
              badge={calendarPreviewEvents.length}
            >
              <Button
                variant="outline"
                onClick={() => setCalendarModalOpen(true)}
                className="w-full justify-between"
              >
                <span>Open calendar view</span>
                <Calendar className="h-4 w-4" />
              </Button>
            </CollapsibleSection>

            {/* Status / Reassurance Section */}
            <CollapsibleSection
              id="status"
              title="Status / Reassurance"
              icon={Heart}
              isExpanded={expandedSections.has("status")}
              onToggle={() => toggleSection("status")}
              isMuted={isMuted}
            >
              <div className="rounded-lg bg-muted/30 p-4">
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {getContextMessage()}
                </p>
              </div>
            </CollapsibleSection>
          </div>
        </>
      )}
    </aside>
  );
}
