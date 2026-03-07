# Session History And Focus Layout Design

## Summary

This design introduces a first-class `session` model to represent one planning conversation followed by one focus run. The focus screen keeps the timer as the primary UI while preserving planning context in a collapsed, expandable panel. Completed or stopped sessions are archived and become searchable through a dedicated history entry in the sidebar.

## Goals

- Keep the active focus timer visually dominant after planning ends.
- Preserve the planning conversation inside the active focus experience.
- Archive completed planning/focus sessions as reviewable records.
- Let users browse archived sessions from a dedicated sidebar entry.

## Non-Goals

- Multi-focus-task sessions under one planning conversation.
- Cross-device sync or backend-backed session storage.
- Converting thought parking into the same archive timeline.

## Current State

- Planning and focus are separate full-screen modes switched by `userState`.
- Planning messages live in `planningMessages` and are cleared when planning mode mounts.
- Persisted state only keeps unfinished tasks and thought parking items.
- There is no concept of session history or archived focus runs.

## Proposed Approach

### Session As The Core Record

Add a `SessionRecord` domain object in the client store. A session starts when the user sends the first planning message. The same session collects all planning messages, the selected focus task snapshot, timer metadata, and an end reason once the focus run completes or is stopped.

Recommended shape:

```ts
interface SessionRecord {
  id: string;
  title: string;
  status: "planning" | "focusing" | "archived";
  startedAt: Date;
  endedAt?: Date;
  endReason?: "completed" | "stopped" | "interrupted";
  taskSnapshot?: {
    id: string;
    title: string;
    description?: string;
    duration: number;
    status: Task["status"];
    startedAt?: Date;
    completedAt?: Date;
  };
  planningMessages: ChatMessage[];
}
```

Store two buckets:

- `activeSession: SessionRecord | null`
- `archivedSessions: SessionRecord[]`

### Focus Layout

When a planning session moves into focus:

- Keep the timer, current task, and controls in the main focus column.
- Add a collapsed `Planning session` panel below or adjacent to the timer content.
- The collapsed panel shows session title, started time, message count, and the latest assistant summary.
- Expanding the panel reveals the full planning chat history inside the focus screen without leaving the timer context.

The panel should default to collapsed to reduce cognitive noise during focus.

### History / Archive Navigation

Add a `History / Archive` entry to the sidebar. This opens a history view that lists archived sessions in reverse chronological order. Each row shows:

- session title
- started time
- end state
- focus task title
- focus duration

Selecting a session opens a detail view that prioritizes the planning transcript first, then the focus result summary.

### Session Lifecycle

Lifecycle rules:

1. First planning message creates `activeSession` if it does not exist.
2. Every planning user/assistant message is appended to both `planningMessages` and `activeSession.planningMessages`.
3. Starting focus updates `activeSession.status` to `focusing` and captures the chosen task snapshot.
4. Finishing the timer archives the session with `endReason = "completed"`.
5. Manually stopping focus archives the session with `endReason = "stopped"`.
6. Entering `interrupted` or `resting` does not end the session by itself.
7. Leaving during planning keeps the session active and resumable.

## Data Persistence

Persist the following client-side through the existing Zustand persist layer:

- `activeSession`
- `archivedSessions`
- `planningMessages` for the current active session

Persist archived sessions separately from unfinished tasks so completed work is reviewable even though completed tasks are currently filtered out. Archived sessions become the source of truth for historical task results.

## Error Handling And Recovery

- Refresh during planning or focus restores `activeSession`, planning transcript, current task, and timer state.
- If session persistence fails, the focus timer should still render and run.
- History screens should show an empty state or lightweight error state rather than breaking the main workflow.

## Testing Strategy

Primary verification targets:

- creating an active session on first planning message
- preserving planning messages into focus mode
- rendering the collapsed planning panel during focus
- expanding the panel to show prior planning transcript
- archiving sessions on timer completion
- archiving sessions on manual stop
- rendering archived session lists and session details in history view

## Risks And Trade-Offs

- Keeping planning state in both `planningMessages` and `activeSession.planningMessages` duplicates data, but it minimizes disruption to current UI code and lowers migration risk.
- Client-only persistence is fast to ship, but history remains device-local.
- Adding history navigation increases app-shell complexity, so route/state ownership should stay centralized in the store.
