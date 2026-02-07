"""Focus Agent (v3) — keeps focus and prevents context drift."""

import datetime
import os
from typing import Optional

from connectonion import Agent, Memory

from agents.model_config import resolve_model
from tools.focus_tools import ContextTool, FocusToolkit
from tools.parking_tools import ParkingService, ParkingToolkit
from tools.plan_tools_v2 import PlanManager
from tools.reward_tools import RewardToolkit


DEFAULT_MODEL = "co/gemini-3-pro-preview"
FINISHED_MARKER = "<<FINISHED>>"
STATUS_CONTINUE = "CONTINUE"
STATUS_FINISHED = "FINISHED"

FOCUS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "focus_prompt.md"
)
try:
    with open(FOCUS_PROMPT_PATH, "r", encoding="utf-8") as f:
        FOCUS_PROMPT = f.read()
except Exception as e:
    FOCUS_PROMPT = f"Error loading system prompt: {e}"


class FocusAgent:
    """Anchor execution-stage context and provide lightweight guidance."""

    def __init__(
        self,
        model: Optional[str] = None,
        plan_manager: Optional[PlanManager] = None,
        context_tool: Optional[ContextTool] = None,
        toolkit: Optional[FocusToolkit] = None,
        parking_service: Optional[ParkingService] = None,
        reward_toolkit: Optional[RewardToolkit] = None,
        memory: Optional[Memory] = None,
    ):
        model = resolve_model(model)
        self.plan_manager = plan_manager or PlanManager()
        self.context_tool = context_tool or ContextTool(
            plan_dir=self.plan_manager.plan_dir
        )
        self.reward_toolkit = reward_toolkit or RewardToolkit(
            brain_dir=self.plan_manager.plan_dir
        )
        self.toolkit = toolkit or FocusToolkit(
            plan_manager=self.plan_manager,
            context_tool=self.context_tool,
            reward_toolkit=self.reward_toolkit,
        )
        self.parking_service = parking_service or ParkingService()
        self.parking_toolkit = ParkingToolkit(service=self.parking_service)
        self.memory = memory
        tools = [self.context_tool, self.toolkit, self.parking_toolkit]
        if self.memory:
            tools.append(self.memory)

        self.agent = Agent(
            name="focus_agent_v3",
            model=model,
            system_prompt=FOCUS_PROMPT,
            tools=tools,
            quiet=True,
            max_iterations=12,
        )

    def handle(self, user_input: str) -> dict:
        """Single-turn entrypoint; inject System Context to avoid drift."""
        idle_alert = user_input.strip().startswith("[IDLE_ALERT]")
        routine_check = user_input.strip().startswith("[ROUTINE_CHECK]")

        if self.parking_service._session_id is None:
            self.parking_service.start_session()
        payload = self._build_payload(user_input)
        try:
            raw = self.agent.input(payload)
        except Exception as exc:
            return {"content": f"[FocusAgent Error] {exc}", "status": STATUS_FINISHED}

        if not isinstance(raw, str):
            return {"content": str(raw), "status": STATUS_FINISHED}

        if FINISHED_MARKER in raw:
            content = raw.replace(FINISHED_MARKER, "").strip()
            parking_summary = self.parking_service.end_session()
            if parking_summary and not parking_summary.startswith("📭"):
                content = f"{content}\n\n---\n{parking_summary}"
            status = STATUS_FINISHED
        else:
            content = raw.strip()
            status = STATUS_CONTINUE

        # System-triggered alerts (Idle Alert / Routine Check) are single-shot;
        # after sending, we consider this turn finished and wait for user input.
        if idle_alert or routine_check:
            status = STATUS_FINISHED

        return {"content": content, "status": status}

    __call__ = handle

    # -- Internal methods --

    def _build_payload(self, user_input: str) -> str:
        context_block = self._render_context_block()
        sanitized_input = user_input.strip()
        return f"{context_block}\n[User Input]\n{sanitized_input}"

    def _render_context_block(self) -> str:
        now = datetime.datetime.now().astimezone()
        now_text = now.strftime("%Y-%m-%d %H:%M %Z")
        active_window = self.context_tool.get_active_window()
        focus_state = self.context_tool.get_focus_state()

        lines = ["[System Context]"]
        lines.append(f"Current Time: {now_text}")
        lines.append(f"Active Window: {active_window}")

        if isinstance(focus_state, dict):
            status = focus_state.get("status", "unknown")
            active_task = focus_state.get("active_task") or {}
            title = active_task.get("title") or "-"
            start = active_task.get("start") or "-"
            end = active_task.get("end") or "-"
            remaining = active_task.get("remaining_minutes")
            plan_path = focus_state.get("plan_path") or "not found"
            progress = focus_state.get("progress") or {}
            done = progress.get("done", 0)
            total = progress.get("total", 0)
            lines.append(f"Active Task: {title}")
            lines.append(f"Task Window: {start} - {end} | Status={status}")
            if remaining is not None and status == "current":
                lines.append(f"Remaining Minutes: {remaining}")
            lines.append(f"Plan Path: {plan_path}")
            lines.append(f"Progress: {done}/{total}")
        else:
            lines.append(f"Active Task: (unavailable) {focus_state}")

        return "\n".join(lines)
