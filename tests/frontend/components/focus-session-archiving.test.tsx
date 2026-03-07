import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FocusMode } from "@/components/focus-mode";
import { useAppStore } from "@/lib/store";

vi.mock("@/app/utils/api", () => ({
  api: {
    getFocusState: vi.fn().mockResolvedValue({}),
    parkThought: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock("@/components/timer-display", () => ({
  TimerDisplay: () => <div>Timer</div>,
}));

describe("focus session archiving", () => {
  beforeEach(() => {
    useAppStore.persist.clearStorage();
    useAppStore.setState(useAppStore.getInitialState(), true);
  });

  it("archives the active session when the timer reaches zero", () => {
    useAppStore.setState({
      userState: "focusing",
      currentTask: {
        id: "task-1",
        title: "Inbox zero",
        duration: 25,
        status: "in-progress",
        createdAt: new Date("2026-03-07T09:00:00Z"),
      },
      activeSession: {
        id: "session-1",
        title: "Morning plan",
        status: "focusing",
        startedAt: new Date("2026-03-07T09:00:00Z"),
        planningMessages: [],
        taskSnapshot: {
          id: "task-1",
          title: "Inbox zero",
          duration: 25,
          status: "in-progress",
        },
      },
      isTimerRunning: true,
      timeRemaining: 0,
      archivedSessions: [],
    });

    render(<FocusMode />);

    expect(useAppStore.getState().activeSession).toBeNull();
    expect(useAppStore.getState().archivedSessions[0]?.endReason).toBe(
      "completed"
    );
  });
});
