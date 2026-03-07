"use client";

import { useMemo, useState } from "react";
import { Clock3, MessageSquareText } from "lucide-react";

import { type SessionRecord } from "@/lib/session-record";

interface HistoryModeProps {
  sessions: SessionRecord[];
}

const formatDateTime = (value?: Date) => {
  if (!value) {
    return "No timestamp";
  }

  return value.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const formatDuration = (minutes?: number) => {
  if (!minutes) {
    return "No duration";
  }

  return `${minutes} min`;
};

export function HistoryMode({ sessions }: HistoryModeProps) {
  const sortedSessions = useMemo(
    () =>
      [...sessions].sort(
        (a, b) => b.startedAt.getTime() - a.startedAt.getTime()
      ),
    [sessions]
  );
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    sortedSessions[0]?.id ?? null
  );

  const selectedSession =
    sortedSessions.find((session) => session.id === selectedSessionId) ??
    sortedSessions[0] ??
    null;

  if (sortedSessions.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-3xl border border-dashed border-border bg-card/40 p-8 text-center">
        <div>
          <h2 className="text-xl font-semibold text-foreground">No archived sessions yet</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Finished planning and focus sessions will show up here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid flex-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section className="rounded-3xl border border-border bg-card/70 p-4">
        <div className="mb-4">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            History / Archive
          </p>
          <h2 className="mt-2 text-xl font-semibold text-foreground">
            Past sessions
          </h2>
        </div>

        <div className="space-y-3">
          {sortedSessions.map((session) => {
            const isActive = session.id === selectedSession?.id;

            return (
              <button
                key={session.id}
                type="button"
                onClick={() => setSelectedSessionId(session.id)}
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  isActive
                    ? "border-primary bg-primary/8"
                    : "border-border bg-background/60 hover:bg-muted/40"
                }`}
              >
                <h3 className="text-sm font-semibold text-foreground">
                  {session.title}
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDateTime(session.startedAt)}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {session.taskSnapshot?.title ?? "No task snapshot"}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-border bg-card/70 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
              Session detail
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">
              {selectedSession?.title}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {formatDateTime(selectedSession?.startedAt)} to{" "}
              {formatDateTime(selectedSession?.endedAt)}
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Clock3 className="h-4 w-4" />
              <span>{formatDuration(selectedSession?.taskSnapshot?.duration)}</span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <MessageSquareText className="h-4 w-4" />
              <span>{selectedSession?.planningMessages.length ?? 0} messages</span>
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-background/60 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Planning transcript
          </p>
          <div className="mt-4 space-y-3">
            {selectedSession?.planningMessages.length ? (
              selectedSession.planningMessages.map((message) => (
                <div
                  key={message.id}
                  className="rounded-2xl border border-border/80 bg-card px-4 py-3"
                >
                  <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    {message.role}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                    {message.content}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                No planning transcript captured for this session.
              </p>
            )}
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-background/60 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Focus result
          </p>
          <p className="mt-3 text-sm text-foreground">
            Task: {selectedSession?.taskSnapshot?.title ?? "No task recorded"}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Ended as: {selectedSession?.endReason ?? "Unknown"}
          </p>
        </div>
      </section>
    </div>
  );
}
