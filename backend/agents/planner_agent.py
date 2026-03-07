"""PlannerAgent (V2) — core time planner."""

import os
import warnings

# Ignore connectonion warning about long prompts being treated as file paths.
warnings.filterwarnings(
    "ignore", category=UserWarning, module="connectonion.core.agent"
)

from typing import Optional

from connectonion import Agent, GoogleCalendar, Memory

from agents.model_config import resolve_model
from tools.plan_tools_v2 import PlanManager


DEFAULT_MODEL = "co/gemini-3-pro-preview"
FINISHED_MARKER = "<<FINISHED>>"
STATUS_CONTINUE = "CONTINUE"
STATUS_FINISHED = "FINISHED"

PLANNER_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "planner_prompt.md"
)
try:
    with open(PLANNER_PROMPT_PATH, "r", encoding="utf-8") as f:
        PLANNER_PROMPT = f.read()
except Exception as e:
    PLANNER_PROMPT = f"Error loading system prompt: {e}"


class CalendarFallback:
    """Fallback when Google Calendar is not available."""

    def __init__(self, reason: str):
        self.reason = reason

    def create_event(
        self,
        title: str,
        start_time: str = None,
        end_time: str = None,
        start: str = None,
        end: str = None,
    ) -> str:
        return f"Calendar unavailable ({self.reason}); skip create_event for {title} {start_time or start} -> {end_time or end}."


class PlannerAgent:
    """Planner Agent wrapper for routing or standalone use."""

    def __init__(
        self,
        model: Optional[str] = None,
        plan_manager: Optional[PlanManager] = None,
        calendar: Optional[object] = None,
        memory: Optional[Memory] = None,
    ):
        model = resolve_model(model)
        self.calendar = calendar or self._init_calendar()
        self.plan_manager = plan_manager or PlanManager(calendar=self.calendar)
        self.memory = memory

        # Patch: inject calendar if plan_manager was constructed without one.
        if self.plan_manager.calendar is None:
            self.plan_manager.calendar = self.calendar

        tools = [self.plan_manager]
        if self.memory:
            tools.append(self.memory)

        self.agent = Agent(
            name="planner_agent_v2",
            model=model,
            system_prompt=PLANNER_PROMPT,
            tools=tools,
            quiet=False,  # Enable logs for debugging tool calls
            max_iterations=20,
        )

    def _init_calendar(self):
        try:
            return GoogleCalendar()
        except Exception as exc:
            return CalendarFallback(str(exc))

    def handle(self, user_input: str) -> dict:
        """
        Single-turn entrypoint; returns an envelope with content/status.
        status:
        - CONTINUE: keep session lock
        - FINISHED: release lock
        """
        raw = self.agent.input(user_input)

        if not isinstance(raw, str):
            return {"content": str(raw), "status": STATUS_FINISHED}

        if FINISHED_MARKER in raw:
            content = raw.replace(FINISHED_MARKER, "").strip()
            status = STATUS_FINISHED
        else:
            content = raw
            status = STATUS_CONTINUE

        return {"content": content, "status": status}

    __call__ = handle
