import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionPlanningPanel } from "@/components/session-planning-panel";

describe("SessionPlanningPanel", () => {
  it("starts collapsed and expands to show transcript", () => {
    render(
      <SessionPlanningPanel
        session={{
          id: "s1",
          title: "Morning plan",
          status: "focusing",
          startedAt: new Date("2026-03-07T09:00:00Z"),
          planningMessages: [
            {
              id: "m1",
              role: "user",
              content: "I need help planning my morning",
              timestamp: new Date("2026-03-07T09:00:00Z"),
              channel: "planning",
            },
            {
              id: "m2",
              role: "assistant",
              content: "Let's start with one 25 minute box.",
              timestamp: new Date("2026-03-07T09:01:00Z"),
              channel: "planning",
            },
          ],
        }}
      />
    );

    expect(
      screen.queryByText("I need help planning my morning")
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /planning session/i }));

    expect(
      screen.getByText("I need help planning my morning")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Let's start with one 25 minute box.")
    ).toBeInTheDocument();
  });
});
