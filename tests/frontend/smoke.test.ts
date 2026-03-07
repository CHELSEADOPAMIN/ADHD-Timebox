import { describe, expect, it } from "vitest";

describe("frontend test harness", () => {
  it("runs vitest in jsdom", () => {
    expect(typeof window).toBe("object");
    expect(document).toBeDefined();
  });
});
