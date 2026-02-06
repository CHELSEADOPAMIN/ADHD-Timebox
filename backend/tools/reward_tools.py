"""Reward toolkit: cowsay-based ASCII rewards and daily summary logging."""

import datetime
import os
import random
import textwrap
from typing import List, Optional

from core.paths import resolve_data_root
try:  # Optional dependency
    import cowsay  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    cowsay = None


# Lightweight praise phrases to avoid calling the LLM every time.
MICRO_PHRASES = [
    "Full power, target hit!",
    "Nice work, dopamine +1.",
    "Cooldown complete, next level!",
    "Small steps, steady combo.",
    "Clean finish, keep the rhythm.",
    "One clean strike, slick and sharp.",
    "Progress bar unlocked, +1.",
    "Loot drop: confidence +5.",
]

MACRO_PHRASES = [
    "Main quest cleared, claim your loot.",
    "Full-day run complete, XP surged!",
    "Boss down. Collect your rewards.",
    "Epic moment. Raise the banner.",
]

# cowsay small and large/rare character lists (filtered at runtime for availability).
SMALL_CHARACTERS = ["cow", "kitty", "pig", "turtle", "turkey", "fox", "cheese", "daemon", "octopus"]
BIG_CHARACTERS = ["dragon", "stegosaurus", "tux", "trex"]


class RewardToolkit:
    """Wrap cowsay reward output and summary logging."""

    def __init__(self, brain_dir: Optional[str] = None, log_dir: Optional[str] = None):
        self.brain_dir = brain_dir or resolve_data_root()
        self.log_dir = log_dir or os.path.join(self.brain_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self._has_cowsay = cowsay is not None
        self._available_chars = set(getattr(cowsay, "char_names", SMALL_CHARACTERS)) if cowsay else set()

    # -- Public methods ------------------------------------------------

    def get_random_character(self, is_big: bool = False) -> str:
        """Return a random cowsay character, optionally favoring large ones."""
        pool = self._filter_available(BIG_CHARACTERS if is_big else SMALL_CHARACTERS)
        if not pool:  # Fall back to all characters, then default cow.
            pool = self._filter_available(SMALL_CHARACTERS + BIG_CHARACTERS) or ["cow"]
        return random.choice(pool)

    def get_hype_phrase(self, is_macro: bool = False) -> str:
        """Return a random hype phrase; macro uses MACRO, otherwise MICRO."""
        pool = MACRO_PHRASES if is_macro else MICRO_PHRASES
        return random.choice(pool)

    def generate_micro_reward(self, task_name: Optional[str] = None) -> str:
        """
        Generate a micro-task ASCII reward using local phrases for low latency.
        """
        title = (task_name or "this task").strip()
        phrase = self.get_hype_phrase(is_macro=False)
        message = f"Done \"{title}\"! {phrase}"
        return self._render(message, is_big=False)

    def generate_macro_reward(self, summary_text: str) -> str:
        """Generate a macro/day-end ASCII reward."""
        phrase = self.get_hype_phrase(is_macro=True)
        combined = f"{summary_text.strip()}\n—— {phrase}"
        return self._render(combined, is_big=True)

    def save_daily_summary(
        self,
        plan_date: datetime.date,
        summary_text: str,
        completed_tasks: Optional[List[dict]] = None,
    ) -> str:
        """Persist daily summary to disk and return the saved path."""
        date_str = plan_date.isoformat()
        path = os.path.join(self.log_dir, f"daily_summary_{date_str}.md")
        lines = [
            f"# Daily Summary {date_str}",
            "",
            summary_text.strip(),
        ]
        tasks = completed_tasks or []
        if tasks:
            lines.append("")
            lines.append("## Completed Tasks")
            for task in tasks:
                title = task.get("title") or task.get("id") or "Task"
                start = task.get("start") or "-"
                end = task.get("end") or "-"
                lines.append(f"- {title} ({start} - {end})")
        content = "\n".join(lines).rstrip() + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    # -- Internal methods ---------------------------------------------

    def _filter_available(self, candidates: List[str]) -> List[str]:
        if not self._has_cowsay:
            return candidates
        return [c for c in candidates if c in self._available_chars]

    def _render(self, text: str, is_big: bool = False) -> str:
        """Render with cowsay when available; otherwise use a simple bubble."""
        character = self.get_random_character(is_big=is_big)
        if self._has_cowsay:
            try:
                # get_output_string is the official python-cowsay API
                render_fn = getattr(cowsay, "get_output_string", None)
                if callable(render_fn):
                    return render_fn(character, text)
                # Fall back to same-named function (some versions export it as an attr)
                cow_fn = getattr(cowsay, character, None)
                if callable(cow_fn):
                    return cow_fn(text)
            except Exception:
                pass  # Continue to fallback
        return self._render_fallback(text)

    def _render_fallback(self, text: str) -> str:
        """Fallback bubble rendering when cowsay is unavailable."""
        wrapped = self._wrap(text)
        lines = wrapped.splitlines() or [text]
        width = max(len(line) for line in lines)
        top = " " + "_" * (width + 2)
        bottom = " " + "-" * (width + 2)
        bubble = "\n".join([f"| {line.ljust(width)} |" for line in lines])
        return f"{top}\n{bubble}\n{bottom}\n (•ᴗ•)つ━☆・*"

    @staticmethod
    def _wrap(text: str, width: int = 48) -> str:
        return textwrap.fill(text.strip(), width=width)
