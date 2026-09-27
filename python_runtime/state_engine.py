"""
Panther Agent - State Engine
Strict, atomic state machine governing the execution lifecycle:
IDLE -> OBSERVE -> REASON -> ACT -> VERIFY -> GOAL_CHECK -> COMPLETE / RECOVERY
"""

import logging
from typing import Dict, Set
from database import DatabaseManager

logger = logging.getLogger("panther.state_engine")

class AgentState:
    IDLE = "IDLE"
    OBSERVE = "OBSERVE"
    REASON = "REASON"
    ACT = "ACT"
    VERIFY = "VERIFY"
    GOAL_CHECK = "GOAL_CHECK"
    COMPLETE = "COMPLETE"
    RECOVERY = "RECOVERY"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# Authorized transitions
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    AgentState.IDLE: {AgentState.OBSERVE, AgentState.CANCELLED},
    AgentState.OBSERVE: {AgentState.OBSERVE, AgentState.REASON, AgentState.RECOVERY, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.REASON: {AgentState.ACT, AgentState.GOAL_CHECK, AgentState.RECOVERY, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.ACT: {AgentState.VERIFY, AgentState.RECOVERY, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.VERIFY: {AgentState.GOAL_CHECK, AgentState.RECOVERY, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.GOAL_CHECK: {AgentState.COMPLETE, AgentState.OBSERVE, AgentState.RECOVERY, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.RECOVERY: {AgentState.OBSERVE, AgentState.ACT, AgentState.GOAL_CHECK, AgentState.FAILED, AgentState.PAUSED, AgentState.CANCELLED},
    AgentState.PAUSED: {AgentState.OBSERVE, AgentState.REASON, AgentState.ACT, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.COMPLETE: {AgentState.IDLE},
    AgentState.FAILED: {AgentState.IDLE},
    AgentState.CANCELLED: {AgentState.IDLE},
}

class StateEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.current_state = AgentState.IDLE
        self._current_task_id = None

    def transition(self, target_state: str, task_id: str, reason: str = "") -> bool:
        """Atomically transitions to target state if authorized."""
        if self.current_state == target_state:
            return True

        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        if target_state not in allowed:
            err = f"Illegal state transition requested: {self.current_state} -> {target_state} (Reason: {reason})"
            logger.error(err)
            self.db.log_diagnostic("ERROR", "StateEngine", err, {
                "current_state": self.current_state,
                "target_state": target_state,
                "task_id": task_id
            })
            return False

        old_state = self.current_state
        self.current_state = target_state
        self._current_task_id = task_id

        logger.info("[StateEngine] State change for task %s: %s -> %s (%s)", task_id, old_state, target_state, reason)
        self.db.log_diagnostic("INFO", "StateEngine", f"Transitioned to {target_state}", {
            "from": old_state,
            "to": target_state,
            "task_id": task_id,
            "reason": reason
        })
        return True

    def reset_to_idle(self):
        self.current_state = AgentState.IDLE
        self._current_task_id = None
