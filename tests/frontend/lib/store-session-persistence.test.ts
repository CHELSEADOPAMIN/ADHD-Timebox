import { beforeEach, describe, expect, it } from "vitest";

import { useAppStore } from "@/lib/store";

describe("session persistence in app store", () => {
  beforeEach(() => {
    useAppStore.persist.clearStorage();
    useAppStore.setState(useAppStore.getInitialState(), true);
  });

  it("creates an active session when the first planning message is added", () => {
    useAppStore.getState().addPlanningMessage({
      id: "m1",
      role: "user",
      content: "Plan my morning",
      timestamp: new Date("2026-03-07T09:00:00Z"),
      channel: "planning",
    });

    expect(useAppStore.getState().activeSession?.planningMessages).toHaveLength(1);
    expect(useAppStore.getState().activeSession?.title).toBe("Plan my morning");
  });

  it("archives the active session when requested", () => {
    const store = useAppStore.getState();

    store.addPlanningMessage({
      id: "m1",
      role: "user",
      content: "Plan my morning",
      timestamp: new Date("2026-03-07T09:00:00Z"),
      channel: "planning",
    });

    store.archiveActiveSession("completed", new Date("2026-03-07T09:30:00Z"));

    expect(useAppStore.getState().activeSession).toBeNull();
    expect(useAppStore.getState().archivedSessions).toHaveLength(1);
    expect(useAppStore.getState().archivedSessions[0]?.endReason).toBe("completed");
  });
});
