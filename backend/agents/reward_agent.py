"""Reward Agent: celebrates wins and crafts daily summaries."""

import datetime
import json
import os
from typing import List, Optional, Tuple

from connectonion import Agent

from agents.model_config import resolve_model
from tools.plan_tools_v2 import PlanManager
from tools.reward_tools import RewardToolkit


DEFAULT_MODEL = "co/gemini-3-pro-preview"

SUMMARY_SYSTEM_PROMPT = """
You are the user's epic bard and hype man.
- Tone: fiery, humorous, cinematic; avoid polite fluff.
- Length: within 50 words.
- Task: the user has already seen the task list; give a punchy or playful celebration and do not repeat the list.
- Language: You MUST respond ONLY in English. Never use Chinese or any other language.
""".strip()


class RewardAgent:
    """Agent that delivers micro-rewards and daily summaries."""

    def __init__(
        self,
        model: Optional[str] = None,
        plan_manager: Optional[PlanManager] = None,
        toolkit: Optional[RewardToolkit] = None,
    ):
        model = resolve_model(model)
        self.plan_manager = plan_manager or PlanManager()
        self.toolkit = toolkit or RewardToolkit(brain_dir=self.plan_manager.plan_dir)
        self.agent = Agent(
            name="reward_agent",
            model=model,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            tools=[],
            quiet=True,
        )

    # -- Public interface ---------------------------------------------

    def celebrate_task(self, task_name: str) -> str:
        """Generate an instant reward using local phrases."""
        return self.toolkit.generate_micro_reward(task_name)

    def summarize_day(self, tasks_data: Optional[List[dict]] = None) -> str:
        """
        Summarize completed tasks for the day, call the LLM for a short celebration,
        and render with a large cowsay character.
        tasks_data: optional task list; if omitted, load today's plan or the latest daily_tasks.
        """
        tasks, plan_date, err = self._resolve_tasks(tasks_data)
        if err:
            return err

        completed = self._filter_completed(tasks)
        if not completed:
            return "📭 No completed tasks marked today yet. Finish a few and come back."

        report_text = self._format_task_report(completed)
        summary_text = self._draft_summary(report_text, plan_date)
        reward_art = self.toolkit.generate_macro_reward(summary_text)
        log_path = self.toolkit.save_daily_summary(
            plan_date=plan_date, summary_text=summary_text, completed_tasks=completed
        )
        header = f"📅 {plan_date.isoformat()} Daily Report"
        separator = "-" * 30
        body = (
            f"{header}\n"
            f"{separator}\n"
            f"{report_text}\n"
            f"{separator}\n\n"
            f"{reward_art}\n\n"
            f"🗂 Archived at: {log_path}"
        )
        return body

    # -- Internal methods ---------------------------------------------

    def _resolve_tasks(
        self, tasks_data: Optional[List[dict]]
    ) -> Tuple[Optional[List[dict]], datetime.date, Optional[str]]:
        """Load tasks from input or disk and return (tasks, plan_date, error)."""
        plan_date = datetime.date.today()

        if tasks_data is not None:
            if not isinstance(tasks_data, list):
                return None, plan_date, "❌ summarize_day expects a list of tasks."
            return tasks_data, plan_date, None

        path = self._locate_plan_path()
        if not path:
            return None, plan_date, "❌ No plan file found for today or recent days."

        try:
            with open(path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception as exc:
            return None, plan_date, f"❌ Failed to read plan: {exc}"

        plan_date = self.plan_manager._plan_date_from_path(path)
        if not isinstance(tasks, list):
            return None, plan_date, f"❌ Invalid plan file format: {path}"
        return tasks, plan_date, None

    def _locate_plan_path(self) -> Optional[str]:
        """Prefer today's plan; fall back to the most recent daily_tasks file."""
        today = datetime.date.today().isoformat()
        today_path = os.path.join(
            self.plan_manager.plan_dir, f"daily_tasks_{today}.json"
        )
        if os.path.exists(today_path):
            return today_path
        candidates = sorted(
            f
            for f in os.listdir(self.plan_manager.plan_dir)
            if f.startswith("daily_tasks_") and f.endswith(".json")
        )
        if not candidates:
            return None
        return os.path.join(self.plan_manager.plan_dir, candidates[-1])

    def _filter_completed(self, tasks: List[dict]) -> List[dict]:
        """Filter completed tasks; allow status=done/completed/complete."""
        completed = []
        for task in tasks:
            status = str(task.get("status") or "").lower()
            if status in {"done", "completed", "complete"}:
                completed.append(task)
        return completed

    def _format_task_report(self, completed: List[dict]) -> str:
        """Generate a concise completion report."""
        lines = []
        for idx, task in enumerate(completed, start=1):
            title = task.get("title") or task.get("id") or f"Task {idx}"
            start = task.get("start") or "-"
            end = task.get("end") or "-"
            lines.append(f"{idx}. ✅ {title}（{start} - {end}）")
        return "\n".join(lines)

    def _draft_summary(self, report_text: str, plan_date: datetime.date) -> str:
        prompt = (
            f"Date: {plan_date.isoformat()}\n"
            f"Completed tasks:\n{report_text}\n\n"
            "The task list has already been shown to the user. In 50 words or fewer, "
            "write a celebration/praise without repeating the list. Tone can be fiery or playful."
        )
        try:
            result = self.agent.input(prompt)
            return result.strip() if isinstance(result, str) else str(result)
        except Exception as exc:  # pragma: no cover - LLM dependency
            fallback = "Main quest complete. Manual applause!"
            return f"{fallback} (model unavailable: {exc})"
