import { describe, expect, it } from "vitest";

import {
  archiveSession,
  createSessionFromMessage,
  startFocusForSession,
} from "@/lib/session-record";

describe("session lifecycle helpers", () => {
  it("creates a planning session from the first message", () => {
    const timestamp = new Date("2026-03-07T09:00:00Z");
    const session = createSessionFromMessage("Write quarterly update", timestamp);

    expect(session.status).toBe("planning");
    expect(session.startedAt).toEqual(timestamp);
    expect(session.planningMessages).toHaveLength(1);
    expect(session.planningMessages[0]?.content).toBe("Write quarterly update");
  });

  it("marks a session as focusing and stores a task snapshot", () => {
    const session = createSessionFromMessage(
      "Plan my morning",
      new Date("2026-03-07T09:00:00Z")
    );

    const next = startFocusForSession(session, {
      id: "task-1",
      title: "Inbox zero",
      duration: 25,
      status: "in-progress",
    });

    expect(next.status).toBe("focusing");
    expect(next.taskSnapshot?.title).toBe("Inbox zero");
    expect(next.taskSnapshot?.duration).toBe(25);
  });

  it("archives a session with an end reason", () => {
    const endedAt = new Date("2026-03-07T09:30:00Z");
    const session = createSessionFromMessage(
      "Plan my morning",
      new Date("2026-03-07T09:00:00Z")
    );

    const archived = archiveSession(session, "completed", endedAt);

    expect(archived.status).toBe("archived");
    expect(archived.endReason).toBe("completed");
    expect(archived.endedAt).toEqual(endedAt);
  });
});
