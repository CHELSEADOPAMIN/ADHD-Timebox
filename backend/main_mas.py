"""Phase 1 entrypoint for the MAS orchestrator."""

from agents.orchestrator import OrchestratorAgent


def main():
    orchestrator = OrchestratorAgent()
    print("🛡️ 多智能体系统 (Phase 1) 已启动...")
    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() in {"q", "quit", "exit"}:
            print("👋 系统退出，再见。")
            break
        try:
            orchestrator.route(user_input)
        except KeyboardInterrupt:
            print("\n👋 系统退出，再见。")
            break
        except Exception as exc:
            print(f"[错误] {exc}")


if __name__ == "__main__":
    main()
