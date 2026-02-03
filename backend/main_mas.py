"""Phase 1 entrypoint for the MAS orchestrator."""

from agents.orchestrator import OrchestratorAgent
from tools.idle_watcher import IdleWatcher


def _build_idle_handler(orchestrator: OrchestratorAgent):
    def _on_idle(payload):
        try:
            event_type = payload.get("type", "idle_alert")
            idle_seconds = int(payload.get("idle_seconds") or 0)
            idle_minutes = max(idle_seconds // 60, 1)
            window = payload.get("active_window") or "unknown window"
            focus_state = (
                payload.get("focus_state") if isinstance(payload, dict) else {}
            )
            active_task = (
                focus_state.get("active_task") if isinstance(focus_state, dict) else {}
            )
            task_title = (active_task or {}).get("title") or "current task"

            if event_type == "routine_check":
                # Routine check: only check context relevance, no idle time.
                message = (
                    f"[ROUTINE_CHECK] Active window: {window}. Active task: {task_title}"
                )
            else:
                # Default idle alert
                message = (
                    f"[IDLE_ALERT] Idle for about {idle_minutes} minutes. "
                    f"Active window: {window}. Active task: {task_title}"
                )

            resp = orchestrator.focus_agent.handle(message)
            content = resp.get("content") if isinstance(resp, dict) else str(resp)

            # If routine check and agent wants silence, do not output.
            if event_type == "routine_check" and "<<SILENCE>>" in content:
                return

            # Strip marker and display content.
            display_content = content.replace("<<SILENCE>>", "").strip()
            if not display_content:
                return

            header = "⚠️ Distraction Alert" if event_type == "idle_alert" else "🛡️ Context Check"
            print(f"\n{header}\n{display_content}\n(Tip: type anything to continue)")

        except Exception as exc:
            print(f"[IdleWatcher] Failed to push alert: {exc}")

    return _on_idle


def main():
    orchestrator = OrchestratorAgent()
    idle_watcher = IdleWatcher(
        context_tool=orchestrator.focus_agent.context_tool,
        on_idle=_build_idle_handler(orchestrator),
        interval_seconds=30,
        idle_threshold_seconds=300,  # 5 minutes idle -> alert
        cooldown_seconds=600,  # 10 minutes cooldown
        focus_only=True,
        routine_check_seconds=300,  # check context every 5 minutes
    )
    idle_watcher.start()

    print("\n" + "=" * 40)
    print("🤖 ADHD Tymebox Assistant (MAS) started")
    print("=" * 40)
    print("I can help you stay focused and reduce cognitive load:")
    print("1. 📅 Plan: type 'today I need to...' or 'delay the meeting by 10 minutes'")
    print("2. 🧘 Focus: type 'start task' to enter flow mode")
    print("3. 💡 Park thoughts: type 'note this...' to stash distractions")
    print("-" * 40)

    # Check today's tasks
    tasks_summary = orchestrator.plan_manager.list_tasks()
    if "No plan for today" in tasks_summary or "Plan file not found" in tasks_summary:
        print("👇 First time today: what tasks do you want to do?")
    else:
        print("📅 Today's plan:")
        print(tasks_summary)
        print("\n👇 What's next? (e.g., 'start the first task', 'delay 10 minutes')")

    try:
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in {"q", "quit", "exit"}:
                print("👋 Exiting. Bye!")
                break
            try:
                orchestrator.route(user_input)
            except KeyboardInterrupt:
                print("\n👋 Exiting. Bye!")
                break
            except Exception as exc:
                print(f"[Error] {exc}")
    finally:
        idle_watcher.stop()


if __name__ == "__main__":
    main()
