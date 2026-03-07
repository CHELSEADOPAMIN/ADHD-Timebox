"use client";

import { useMemo, useState } from "react";
import { ChevronDown, MessageSquareText } from "lucide-react";

import { type SessionRecord } from "@/lib/session-record";

interface SessionPlanningPanelProps {
  session: SessionRecord;
}

const formatStartedAt = (date: Date) =>
  date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

export function SessionPlanningPanel({ session }: SessionPlanningPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const latestAssistantMessage = useMemo(
    () =>
      [...session.planningMessages]
        .reverse()
        .find((message) => message.role === "assistant"),
    [session.planningMessages]
  );

  return (
    <div className="mt-8 w-full rounded-3xl border border-border bg-card/80 shadow-sm">
      <button
        type="button"
        onClick={() => setIsExpanded((current) => !current)}
        className="flex w-full items-center gap-3 px-5 py-4 text-left"
        aria-expanded={isExpanded}
        aria-label="Planning session"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <MessageSquareText className="h-5 w-5" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Planning session
          </p>
          <p className="mt-1 truncate text-sm font-medium text-foreground">
            {session.title}
          </p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            Started {formatStartedAt(session.startedAt)} · {session.planningMessages.length} messages
            {latestAssistantMessage ? ` · ${latestAssistantMessage.content}` : ""}
          </p>
        </div>

        <ChevronDown
          className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {isExpanded && (
        <div className="border-t border-border px-5 py-4">
          <div className="space-y-3">
            {session.planningMessages.map((message) => (
              <div
                key={message.id}
                className="rounded-2xl border border-border/70 bg-background/70 px-4 py-3"
              >
                <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                  {message.role}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {message.content}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
