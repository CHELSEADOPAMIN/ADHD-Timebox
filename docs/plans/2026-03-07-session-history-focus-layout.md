# Session History Focus Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a session-based planning and focus flow where focus keeps a collapsible planning transcript visible, and finished sessions are archived behind a dedicated sidebar history entry.

**Architecture:** Introduce a first-class session model in the Zustand store, with pure helper functions for lifecycle transitions so behavior can be tested without rendering the full app. Add a lightweight app-level view mode for `history`, render a collapsible planning transcript inside focus mode, and surface archived sessions in a dedicated history screen that prioritizes planning transcript over task outcome.

**Tech Stack:** Next.js App Router, React 19, Zustand persist, TypeScript, Tailwind CSS, Vitest, React Testing Library, jsdom

---

### Task 1: Add Frontend Test Infrastructure

**Files:**
- Modify: `package.json`
- Create: `vitest.config.ts`
- Create: `tests/setup-vitest.ts`
- Create: `tests/frontend/smoke.test.ts`

**Step 1: Write the failing test**

Create `tests/frontend/smoke.test.ts`:

```ts
import { describe, expect, it } from "vitest";

describe("frontend test harness", () => {
  it("runs vitest in jsdom", () => {
    expect(typeof window).toBe("object");
    expect(document).toBeDefined();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/smoke.test.ts`

Expected: FAIL because Vitest config and dependencies are not set up yet.

**Step 3: Write minimal implementation**

- Add dev dependencies for `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, and `@testing-library/user-event`.
- Add script: `"test:frontend": "vitest run"`.
- Create `vitest.config.ts` with `environment: "jsdom"`, path alias support for `@/`, and `setupFiles: ["./tests/setup-vitest.ts"]`.
- Create `tests/setup-vitest.ts` importing `@testing-library/jest-dom/vitest`.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/smoke.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add package.json pnpm-lock.yaml vitest.config.ts tests/setup-vitest.ts tests/frontend/smoke.test.ts
git commit -m "test: add frontend test harness"
```

### Task 2: Add Session Lifecycle Helpers

**Files:**
- Create: `lib/session-record.ts`
- Create: `tests/frontend/lib/session-record.test.ts`

**Step 1: Write the failing test**

Create `tests/frontend/lib/session-record.test.ts` covering:

```ts
import { describe, expect, it } from "vitest";
import {
  appendPlanningMessage,
  archiveSession,
  createSessionFromMessage,
  startFocusForSession,
} from "@/lib/session-record";

describe("session lifecycle helpers", () => {
  it("creates a planning session from the first message", () => {
    const session = createSessionFromMessage("Write quarterly update", new Date("2026-03-07T09:00:00Z"));
    expect(session.status).toBe("planning");
    expect(session.planningMessages).toHaveLength(1);
  });

  it("marks a session as focusing and stores a task snapshot", () => {
    const session = createSessionFromMessage("Plan my morning", new Date("2026-03-07T09:00:00Z"));
    const next = startFocusForSession(session, {
      id: "task-1",
      title: "Inbox zero",
      duration: 25,
      status: "in-progress",
      createdAt: new Date("2026-03-07T09:00:00Z"),
    });
    expect(next.status).toBe("focusing");
    expect(next.taskSnapshot?.title).toBe("Inbox zero");
  });

  it("archives a session with an end reason", () => {
    const session = createSessionFromMessage("Plan my morning", new Date("2026-03-07T09:00:00Z"));
    const archived = archiveSession(session, "completed", new Date("2026-03-07T09:30:00Z"));
    expect(archived.status).toBe("archived");
    expect(archived.endReason).toBe("completed");
    expect(archived.endedAt).toEqual(new Date("2026-03-07T09:30:00Z"));
  });
});
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/lib/session-record.test.ts`

Expected: FAIL with module-not-found for `@/lib/session-record`.

**Step 3: Write minimal implementation**

Create `lib/session-record.ts` with:

- `SessionRecord` and `SessionTaskSnapshot` types
- `createSessionFromMessage(content, timestamp, initialMessage?)`
- `appendPlanningMessage(session, message)`
- `startFocusForSession(session, task)`
- `archiveSession(session, endReason, endedAt)`
- small helpers for deriving title and copying task snapshot

Keep helpers pure and free of store or React imports.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/lib/session-record.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add lib/session-record.ts tests/frontend/lib/session-record.test.ts
git commit -m "feat: add session lifecycle helpers"
```

### Task 3: Persist Active And Archived Sessions In The Store

**Files:**
- Modify: `lib/store.ts`
- Create: `tests/frontend/lib/store-session-persistence.test.ts`

**Step 1: Write the failing test**

Create `tests/frontend/lib/store-session-persistence.test.ts` covering:

```ts
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
  });
});
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/lib/store-session-persistence.test.ts`

Expected: FAIL because `activeSession`, `archivedSessions`, and archive actions do not exist.

**Step 3: Write minimal implementation**

Update `lib/store.ts` to:

- add `AppView = "main" | "history"`
- add `activeSession`, `archivedSessions`, `appView`, `setAppView`
- update `addPlanningMessage` to create/append `activeSession`
- add `setActiveSessionTask(task)`, `archiveActiveSession(endReason, endedAt)`, and `clearActiveSession()`
- persist `activeSession` and `archivedSessions`
- stop clearing `planningMessages` automatically on mount-driven flows
- preserve date fields on migration or rehydrate as needed

Use helpers from `lib/session-record.ts` instead of embedding lifecycle rules inline.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/lib/store-session-persistence.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add lib/store.ts tests/frontend/lib/store-session-persistence.test.ts
git commit -m "feat: persist active and archived sessions"
```

### Task 4: Add History Navigation To The App Shell

**Files:**
- Modify: `components/sidebar.tsx`
- Modify: `components/app-shell.tsx`
- Create: `components/history-mode.tsx`
- Create: `tests/frontend/components/history-mode.test.tsx`

**Step 1: Write the failing test**

Create `tests/frontend/components/history-mode.test.tsx`:

```tsx
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
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/components/history-mode.test.tsx`

Expected: FAIL because `HistoryMode` does not exist.

**Step 3: Write minimal implementation**

- Create `components/history-mode.tsx` with:
  - archive list on the left or top
  - session detail pane that renders planning transcript first
  - task summary below the transcript
  - empty state when there are no archived sessions
- Update `components/sidebar.tsx` to add a `History / Archive` control wired to `setAppView("history")`
- Update `components/app-shell.tsx` to render `HistoryMode` when `appView === "history"` and the normal mode stack otherwise

Keep `HistoryMode` dumb if possible: pass sessions in, let store wiring stay in the shell.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/components/history-mode.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add components/sidebar.tsx components/app-shell.tsx components/history-mode.tsx tests/frontend/components/history-mode.test.tsx
git commit -m "feat: add session archive history view"
```

### Task 5: Keep Planning Transcript Available During Focus

**Files:**
- Create: `components/session-planning-panel.tsx`
- Modify: `components/focus-mode.tsx`
- Create: `tests/frontend/components/session-planning-panel.test.tsx`

**Step 1: Write the failing test**

Create `tests/frontend/components/session-planning-panel.test.tsx`:

```tsx
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

    expect(screen.queryByText("I need help planning my morning")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /planning session/i }));
    expect(screen.getByText("I need help planning my morning")).toBeInTheDocument();
    expect(screen.getByText("Let's start with one 25 minute box.")).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/components/session-planning-panel.test.tsx`

Expected: FAIL because the panel component does not exist.

**Step 3: Write minimal implementation**

- Create `components/session-planning-panel.tsx` as a collapsible transcript panel
- Show session title, started time, message count, and latest assistant line in collapsed mode
- Expand to full planning transcript on click
- Update `components/focus-mode.tsx` to read `activeSession` from the store and render the panel under the timer content

Do not change the intervention modal behavior in this task beyond layout composition.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/components/session-planning-panel.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add components/session-planning-panel.tsx components/focus-mode.tsx tests/frontend/components/session-planning-panel.test.tsx
git commit -m "feat: keep planning transcript visible in focus mode"
```

### Task 6: Connect Session Archiving To Focus Transitions

**Files:**
- Modify: `components/planning-mode.tsx`
- Modify: `components/focus-mode.tsx`
- Create: `tests/frontend/components/focus-session-archiving.test.tsx`

**Step 1: Write the failing test**

Create `tests/frontend/components/focus-session-archiving.test.tsx` covering:

```tsx
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { FocusMode } from "@/components/focus-mode";
import { useAppStore } from "@/lib/store";

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
    });

    render(<FocusMode />);

    expect(useAppStore.getState().activeSession).toBeNull();
    expect(useAppStore.getState().archivedSessions[0]?.endReason).toBe("completed");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/components/focus-session-archiving.test.tsx`

Expected: FAIL because focus completion does not archive sessions.

**Step 3: Write minimal implementation**

- Update `components/planning-mode.tsx` so planning messages no longer get wiped on mount and focus start records the selected task into `activeSession`
- Update `components/focus-mode.tsx` to call `archiveActiveSession("completed", new Date())` when the timer finishes
- Update manual stop path to call `archiveActiveSession("stopped", new Date())`
- Clear or reset transient planning UI only after archiving is complete

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/components/focus-session-archiving.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add components/planning-mode.tsx components/focus-mode.tsx tests/frontend/components/focus-session-archiving.test.tsx
git commit -m "feat: archive sessions on focus completion"
```

### Task 7: Run Final Verification

**Files:**
- Modify: none unless fixes are required

**Step 1: Run targeted frontend tests**

Run:

```bash
pnpm exec vitest run tests/frontend/lib/session-record.test.ts tests/frontend/lib/store-session-persistence.test.ts tests/frontend/components/history-mode.test.tsx tests/frontend/components/session-planning-panel.test.tsx tests/frontend/components/focus-session-archiving.test.tsx
```

Expected: all listed tests PASS

**Step 2: Run lint**

Run: `pnpm lint`

Expected: exit code 0

**Step 3: Run type/build verification**

Run: `pnpm exec tsc --noEmit`

Expected: exit code 0

**Step 4: Commit any final fixes**

```bash
git add .
git commit -m "chore: finalize session history flow"
```
