"""Phase 1 entrypoint for the MAS orchestrator."""

import os
from dotenv import load_dotenv

# 加载 .env 环境变量
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

from agents.orchestrator import OrchestratorAgent


def main():
    orchestrator = OrchestratorAgent()
    print("时间盒助手启动 今日首次登录请输入今天的计划吧！")
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
