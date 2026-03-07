import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HistoryMode } from "@/components/history-mode";

describe("HistoryMode", () => {
  it("shows archived sessions ordered newest first", () => {
    render(
      <HistoryMode
        sessions={[
          {
            id: "older",
            title: "Morning plan",
            status: "archived",
            startedAt: new Date("2026-03-07T08:00:00Z"),
            endedAt: new Date("2026-03-07T08:25:00Z"),
            endReason: "completed",
            planningMessages: [],
            taskSnapshot: {
              id: "t1",
              title: "Write report",
              duration: 25,
              status: "completed",
            },
          },
          {
            id: "newer",
            title: "Afternoon reset",
            status: "archived",
            startedAt: new Date("2026-03-07T10:00:00Z"),
            endedAt: new Date("2026-03-07T10:15:00Z"),
            endReason: "stopped",
            planningMessages: [],
            taskSnapshot: {
              id: "t2",
              title: "Triage email",
              duration: 15,
              status: "partial",
            },
          },
        ]}
      />
    );

    const headings = screen.getAllByRole("heading", { level: 3 });
    expect(headings[0]).toHaveTextContent("Afternoon reset");
    expect(headings[1]).toHaveTextContent("Morning plan");
  });
});
