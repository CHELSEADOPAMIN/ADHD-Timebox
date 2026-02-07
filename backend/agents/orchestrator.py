"""Orchestrator agent for Phase 1 MAS routing."""

import datetime
import json
import os
from typing import Optional

from connectonion import Agent, Memory

from agents.model_config import resolve_model
from agents.focus_agent import FocusAgent
from agents.planner_agent import PlannerAgent
from agents.reward_agent import RewardAgent
from tools.parking_tools import ParkingService
from tools.plan_tools_v2 import PlanManager


SYSTEM_PROMPT = """
You are OrchestratorAgent, the central routing hub of a multi-agent system.
Your job is to calmly and objectively classify user intent.
You MUST output in English only.

### Routing rules
1. PLANNER (schedule manager)
- Use for planning/arranging/rescheduling.
- Keywords: schedule, time, delay, move, plan, tomorrow, today, calendar.
- Chinese examples: "我想规划今天任务", "帮我安排今天", "把会议推迟10分钟".

2. FOCUS (execution coach)
- Use for in-task execution, completion, stuck, distraction while executing.
- Keywords: start, finished, stuck, distracted, working on it.
- Chinese examples: "开始第一个任务", "我做完了", "我卡住了", "我走神了".

3. PARKING (thought parking)
- Use for lookup/record/idea capture.
- Keywords: search, look up, remember, idea, note.
- Chinese examples: "查一下这个", "记一下这个想法", "突然想到一个点子".

### Special rule for "我要做/我想做"
- If user says "我要做..." / "我想做..." and it sounds like listing what to do,
  prefer PLANNER when context is unclear.
- If clearly referring to an existing scheduled task already in execution context,
  choose FOCUS.

### Output format (strict)
- If intent matches: CALL: <AGENT_NAME> | <REASON>
- If greeting/unclear: REPLY: <response>

### Examples
User: "delay the current task by 30 minutes"
Output: CALL: PLANNER | time adjustment
User: "I'm ready to start coding"
Output: CALL: FOCUS | task start
User: "look up the exchange rate"
Output: CALL: PARKING | external search
User: "hello"
Output: REPLY: Hi! Tell me what you want to do next.
""".strip()

STATUS_CONTINUE = "CONTINUE"
STATUS_FINISHED = "FINISHED"


class OrchestratorAgent:  # Note: uses composition instead of inheriting Agent
    """Front-of-house router that simulates hand-offs."""

    def __init__(
        self,
        plan_manager: Optional[PlanManager] = None,
        memory_dir: Optional[str] = None,
        brain_dir: Optional[str] = None,
        memory: Optional[Memory] = None,
    ):
        # Warm PlannerAgent; keep PlanManager at router level for context injection.
        self.plan_manager = plan_manager or PlanManager()
        # Shared memory for Planner / Focus / Reward agents.
        resolved_memory_dir = memory_dir or os.path.join(
            self.plan_manager.plan_dir, "long_term_memory"
        )
        self.shared_memory = memory or Memory(memory_dir=resolved_memory_dir)
        self.planner_agent = PlannerAgent(
            plan_manager=self.plan_manager, memory=self.shared_memory
        )
        self.parking_service = ParkingService(
            brain_dir=brain_dir or self.plan_manager.plan_dir
        )
        self.reward_agent = RewardAgent(plan_manager=self.plan_manager)
        self.focus_agent = FocusAgent(
            plan_manager=self.plan_manager,
            parking_service=self.parking_service,
            reward_toolkit=self.reward_agent.toolkit,
            memory=self.shared_memory,
        )
        # Session lock: if set, forward future input directly to the locked agent.
        self.locked_agent = None
        self.escape_words = {"exit", "stop", "unlock", "end", "quit", "terminate"}
        self.last_agent = "orchestrator"

    def route(self, user_input: str) -> str:
        """
        Route user input with exclusive call mechanism:
        - If locked_agent exists, bypass classification and forward directly.
        - Otherwise classify intent, select agent, and update lock per envelope status.
        """
        normalized = user_input.strip().lower()

        if self._is_finish_day_intent(normalized):
            self.locked_agent = None
            summary = self.reward_agent.summarize_day()
            self.last_agent = "reward"
            print(summary)
            return summary

        # Escape hatch: force unlock
        if self.locked_agent and any(word in normalized for word in self.escape_words):
            self.locked_agent = None
            msg = "🔓 Session lock released."
            self.last_agent = "orchestrator"
            print(msg)
            return msg

        # Deterministic override for "我要做/我想做" style starts:
        # - with existing actionable tasks -> FOCUS
        # - without tasks -> PLANNER
        if self._is_do_intent(normalized):
            has_tasks = self._has_actionable_tasks_today()
            agent = self.focus_agent if has_tasks else self.planner_agent
            target = "FOCUS" if has_tasks else "PLANNER"
            reason = (
                "existing actionable tasks; start execution"
                if has_tasks
                else "no actionable tasks; plan first"
            )
            if self.locked_agent and self.locked_agent is not agent:
                self.locked_agent = None
            print(f">> [Router] Intent override to {target}... Reason: {reason}")
            envelope = self._safe_handle(agent, user_input)
            content = envelope.get("content", "")
            self._update_lock(agent, envelope)
            self.last_agent = self._agent_name(agent)
            print(content)
            return content

        # Fast path: locked agent consumes input directly
        if self.locked_agent:
            print(">> [Session Lock] Forwarding to locked agent ...")
            active_agent = self.locked_agent
            envelope = self._safe_handle(active_agent, user_input)
            content = envelope.get("content", "")
            self._update_lock(active_agent, envelope)
            self.last_agent = self._agent_name(active_agent)
            # final_content = self._maybe_attach_daily_reward(content) # Removed auto-reward
            print(content)
            return content

        # Create a fresh, one-off Agent per request to avoid memory residue.
        temp_agent = Agent(
            name="orchestrator_temp",
            system_prompt=SYSTEM_PROMPT,
            model=resolve_model(),
            tools=[],
            quiet=True,  # Reduce noisy logs
        )

        # Force a unique name to avoid any on-disk session reuse.
        import time

        temp_agent.name = f"orchestrator_{int(time.time()*1000)}"

        raw = temp_agent.input(user_input).strip()

        if raw.startswith("CALL:"):
            parts = raw.split("|", 1)
            target = parts[0].replace("CALL:", "").strip().upper()
            reason = parts[1].strip() if len(parts) > 1 else ""
            print(
                f">> [Router] Handoff to {target}...{f' Reason: {reason}' if reason else ''}"
            )

            active_agent = None
            if target == "PLANNER":
                active_agent = self.planner_agent
            elif target == "FOCUS":
                active_agent = self.focus_agent
            elif target == "PARKING":
                result = self.parking_service.dispatch_task(
                    content=user_input, task_type="search", source="orchestrator"
                )
                self.locked_agent = None
                self.last_agent = "parking"
                # final_result = self._maybe_attach_daily_reward(result) # Removed auto-reward
                # Do not print to avoid duplicate output by the caller
                return result

            if not active_agent:
                msg = f"Handling for {target} is not implemented yet."
                self.locked_agent = None
                self.last_agent = "orchestrator"
                print(msg)
                return msg

            envelope = self._safe_handle(active_agent, user_input)
            content = envelope.get("content", "")
            self._update_lock(active_agent, envelope)
            self.last_agent = self._agent_name(active_agent)
            # final_content = self._maybe_attach_daily_reward(content) # Removed auto-reward
            print(content)
            return content

        if raw.startswith("REPLY:"):
            reply = raw.replace("REPLY:", "", 1).strip()
            self.locked_agent = None
            self.last_agent = "orchestrator"
            # final_reply = self._maybe_attach_daily_reward(reply) # Removed auto-reward
            print(reply)
            return reply

        # Fallback
        fallback = f"REPLY: {raw}"
        self.locked_agent = None
        self.last_agent = "orchestrator"
        # final_fallback = self._maybe_attach_daily_reward(fallback) # Removed auto-reward
        print(fallback)
        return fallback

    @staticmethod
    def _agent_name(agent) -> str:
        if agent is None:
            return "orchestrator"
        name = agent.__class__.__name__.lower()
        if "planner" in name:
            return "planner"
        if "focus" in name:
            return "focus"
        if "reward" in name:
            return "reward"
        return name

    def _safe_handle(self, agent, user_input: str) -> dict:
        """Call target Agent.handle and wrap an envelope; Planner injects System State."""
        payload = self._build_payload(agent, user_input)
        try:
            resp = agent.handle(payload)
        except Exception as exc:
            return {
                "content": f"[{agent.__class__.__name__} Error] {exc}",
                "status": STATUS_FINISHED,
            }
        return self._normalize_envelope(resp)

    def _build_payload(self, agent, user_input: str) -> str:
        """Inject plan context for Planner; other agents keep raw input."""
        if isinstance(agent, PlannerAgent):
            return self._inject_plan_context(user_input)
        return user_input

    def _inject_plan_context(self, user_input: str) -> str:
        """Assemble user input with today's plan context."""
        try:
            context = self.plan_manager.get_current_context()
        except Exception as exc:
            context = f"PlanManager.get_current_context failed: {exc}"

        sanitized_input = user_input.strip()
        return f"<User_Input>\n{sanitized_input}\n</User_Input>\n\n<System_State>\n{context}\n</System_State>"

    def _normalize_envelope(self, resp) -> dict:
        """Ensure envelope has content/status; legacy agents default to FINISHED."""
        if isinstance(resp, dict):
            content = resp.get("content", "")
            status = (resp.get("status") or STATUS_FINISHED).upper()
            return {"content": content, "status": status}
        return {"content": str(resp), "status": STATUS_FINISHED}

    def _update_lock(self, agent, envelope: dict):
        status = (
            envelope.get("status") if isinstance(envelope, dict) else STATUS_FINISHED
        ) or STATUS_FINISHED
        if str(status).upper() == STATUS_CONTINUE:
            self.locked_agent = agent
        else:
            self.locked_agent = None

    # -- Reward / summary hooks -----------------------------------------

    def _is_finish_day_intent(self, normalized_input: str) -> bool:
        keywords = [
            "finish day",
            "end of day",
            "today done",
        ]
        return any(key in normalized_input for key in keywords)

    def _is_do_intent(self, normalized_input: str) -> bool:
        patterns = [
            "我要做",
            "我想做",
            "我打算做",
            "i want to do",
            "i need to do",
            "i'm going to do",
            "i am going to do",
        ]
        return any(p in normalized_input for p in patterns)

    def _has_actionable_tasks_today(self) -> bool:
        try:
            today = datetime.date.today().isoformat()
            tasks, _, err = self.plan_manager._load_tasks(today, False)
            if err or not isinstance(tasks, list) or not tasks:
                return False
            for task in tasks:
                status = str(task.get("status") or "").lower()
                if status not in {"done", "completed", "complete"}:
                    return True
            return False
        except Exception:
            return False

    def _maybe_attach_daily_reward(self, content: str) -> str:
        reward = self._auto_reward_if_completed()
        if reward:
            return f"{content}\n\n---\n{reward}" if content else reward
        return content

    def _auto_reward_if_completed(self) -> Optional[str]:
        all_done, plan_date = self._all_tasks_completed()
        if not all_done:
            return None
        log_path = os.path.join(
            self.reward_agent.toolkit.log_dir,
            f"daily_summary_{plan_date.isoformat()}.md",
        )
        if os.path.exists(log_path):
            return None
        return self.reward_agent.summarize_day()

    def _all_tasks_completed(self) -> tuple[bool, datetime.date]:
        plan_path = self.reward_agent._locate_plan_path()
        if not plan_path:
            return False, datetime.date.today()
        plan_date = self.plan_manager._plan_date_from_path(plan_path)
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception:
            return False, plan_date
        if not isinstance(tasks, list) or not tasks:
            return False, plan_date
        statuses = [str(t.get("status") or "").lower() for t in tasks]
        all_done = statuses and all(
            s in {"done", "completed", "complete"} for s in statuses
        )
        return all_done, plan_date
