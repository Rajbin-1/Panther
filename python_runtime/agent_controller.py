"""
Panther Agent - Agent Controller (Stage 2)
Primary orchestrator of the real agent runtime and action loop:
START -> OBSERVE -> BUILD CONTEXT -> REASON -> VALIDATE MODEL OUTPUT -> ACT -> OBSERVE -> VERIFY -> GOAL CHECK -> (COMPLETE / RECOVERY / CONTINUE)
Enforces bounded recovery, ResourceGovernor gating, and deterministic goal completion.
"""

import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple
from database import DatabaseManager
from config_manager import ConfigManager
from resource_governor import ResourceGovernor, ResourcePressure
from screen_observer import ScreenObserver
from action_executor import ActionExecutor
from verification_engine import VerificationEngine, GoalVerifier
from model_manager import ModelManager
from state_engine import StateEngine, AgentState
from screen_state import ScreenState

logger = logging.getLogger("panther.controller")

# Diagnostic Event Constants
EVENT_TURN_STARTED = "TURN_STARTED"
EVENT_OBSERVATION_CREATED = "OBSERVATION_CREATED"
EVENT_MODEL_REQUESTED = "MODEL_REQUESTED"
EVENT_MODEL_RESPONSE_VALIDATED = "MODEL_RESPONSE_VALIDATED"
EVENT_ACTION_EXECUTED = "ACTION_EXECUTED"
EVENT_VERIFICATION_PASSED = "VERIFICATION_PASSED"
EVENT_VERIFICATION_FAILED = "VERIFICATION_FAILED"
EVENT_GOAL_CHECK_PASSED = "GOAL_CHECK_PASSED"
EVENT_GOAL_CHECK_FAILED = "GOAL_CHECK_FAILED"
EVENT_RECOVERY_STARTED = "RECOVERY_STARTED"
EVENT_TASK_PAUSED = "TASK_PAUSED"
EVENT_TASK_CANCELLED = "TASK_CANCELLED"
EVENT_TASK_COMPLETED = "TASK_COMPLETED"
EVENT_TASK_FAILED = "TASK_FAILED"

class AgentController:
    def __init__(
        self,
        db: DatabaseManager,
        config: ConfigManager,
        resource_governor: ResourceGovernor,
        screen_observer: ScreenObserver,
        action_executor: ActionExecutor,
        verification_engine: VerificationEngine,
        goal_verifier: GoalVerifier,
        model_manager: ModelManager,
        state_engine: StateEngine
    ):
        self.db = db
        self.config = config
        self.resource_governor = resource_governor
        self.screen_observer = screen_observer
        self.action_executor = action_executor
        self.verification_engine = verification_engine
        self.goal_verifier = goal_verifier
        self.model_manager = model_manager
        self.state_engine = state_engine

        self._active_task_id: Optional[str] = None
        self._active_task_goal: Optional[str] = None
        self._pause_requested: bool = False
        self._cancel_requested: bool = False
        self._current_step_activity: str = "Ready"
        self._task_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def get_current_status(self) -> Dict[str, Any]:
        """Returns real-time operational status, activity message, and hardware pressure metrics."""
        metrics = self.resource_governor.sample_metrics()
        obs = self.screen_observer.get_current_observation()
        diff = self.screen_observer.get_last_diff()

        return {
            "state": self.state_engine.current_state,
            "active_task_id": self._active_task_id,
            "active_task_goal": self._active_task_goal,
            "activity": self._current_step_activity,
            "is_paused": self._pause_requested,
            "current_observation_id": obs.observation_id if obs else None,
            "active_window": obs.active_window if obs else None,
            "total_nodes": len(obs.nodes) if obs else 0,
            "last_diff_summary": {
                "changed": diff.get("changed", False) if diff else False,
                "text_appeared": diff.get("text_appeared", [])[:5] if diff else [],
                "text_disappeared": diff.get("text_disappeared", [])[:5] if diff else [],
            } if diff else None,
            "resource_metrics": metrics
        }

    def start_task(self, goal: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Initiates a new goal-directed agent task."""
        with self._lock:
            if self._active_task_id and self.state_engine.current_state not in (
                AgentState.IDLE, AgentState.COMPLETE, AgentState.FAILED, AgentState.CANCELLED
            ):
                return {
                    "success": False,
                    "error": f"Agent is busy executing task '{self._active_task_id}' (state: {self.state_engine.current_state})."
                }

            task_id = f"task_{uuid.uuid4().hex[:10]}"
            task_title = title or (goal[:40] + "..." if len(goal) > 40 else goal)

            self._active_task_id = task_id
            self._active_task_goal = goal
            self._pause_requested = False
            self._cancel_requested = False
            self._current_step_activity = "Starting task..."

            # Persist task in SQLite
            self.db.record_task_start(task_id, task_title, goal, AgentState.IDLE)
            self.state_engine.transition(AgentState.OBSERVE, task_id, "Starting task lifecycle loop")

            # Launch asynchronous task thread
            self._task_thread = threading.Thread(
                target=self._run_task_lifecycle,
                args=(task_id, goal),
                daemon=True,
                name=f"PantherRunner-{task_id}"
            )
            self._task_thread.start()

            return {
                "success": True,
                "task_id": task_id,
                "title": task_title,
                "initial_state": AgentState.OBSERVE
            }

    def pause_task(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_task_id:
                return {"success": False, "error": "No active task to pause."}
            self._pause_requested = True
            self._current_step_activity = "Pausing execution before next action..."
            self.db.log_diagnostic("INFO", "AgentController", EVENT_TASK_PAUSED, {"task_id": self._active_task_id})
            return {"success": True, "message": "Pause requested; agent will hold before next action."}

    def resume_task(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_task_id:
                return {"success": False, "error": "No active task to resume."}
            self._pause_requested = False
            # Invalidate observation cache so resume takes a fresh screen capture
            self.screen_observer.invalidate_cache()
            self._current_step_activity = "Resuming task with fresh observation..."
            return {"success": True, "message": "Task resumed."}

    def cancel_task(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_task_id:
                return {"success": False, "error": "No active task to cancel."}
            self._cancel_requested = True
            task_id = self._active_task_id
            self._current_step_activity = "Task cancelled by user."
            self.state_engine.transition(AgentState.CANCELLED, task_id, "Cancelled by user request")
            self.db.update_task_state(task_id, AgentState.CANCELLED, success=False, termination_reason="User cancelled")
            self.db.log_diagnostic("INFO", "AgentController", EVENT_TASK_CANCELLED, {"task_id": task_id})
            return {"success": True, "message": f"Task '{task_id}' marked for immediate cancellation."}

    def _run_task_lifecycle(self, task_id: str, goal: str):
        """
        Bounded Stage 2 Agent Action Loop:
        START -> OBSERVE -> BUILD CONTEXT -> REASON -> ACT -> OBSERVE -> VERIFY -> GOAL CHECK
        """
        logger.info("[Controller] Starting lifecycle loop for task: %s (Goal: %s)", task_id, goal)
        timeouts = self.config.get_section("timeouts")
        retries = self.config.get_section("retries")

        max_turns = self.config.get_value("action_limits", "max_turns_per_task", 10)
        same_action_failure_limit = 2
        verification_failure_limit = 3
        model_error_limit = 2

        turn_index = 0
        turn_history: List[Dict[str, Any]] = []

        # Recovery tracking counters
        action_failures = 0
        verification_failures = 0
        model_errors = 0
        last_action_signature: Optional[str] = None
        consecutive_same_action_count = 0
        last_interaction_pos: Optional[Tuple[int, int]] = None

        try:
            while turn_index < max_turns:
                turn_id = f"{task_id}_turn_{turn_index}"

                # 1. Cancellation Check
                if self._cancel_requested:
                    logger.info("[Controller] Task %s cancelled by user", task_id)
                    self._current_step_activity = "Task cancelled."
                    break

                # 2. Pause Check
                while self._pause_requested:
                    if self.state_engine.current_state != AgentState.PAUSED:
                        self.state_engine.transition(AgentState.PAUSED, task_id, "Execution paused by user")
                    time.sleep(0.4)
                    if self._cancel_requested:
                        break

                if self._cancel_requested:
                    break

                # 3. Resource Governor Check
                can_proceed, reason = self.resource_governor.can_proceed_safely()
                if not can_proceed:
                    logger.warning("[Controller] Resource Governor halted turn %d: %s", turn_index, reason)
                    self._current_step_activity = f"Execution paused: {reason}"
                    self.state_engine.transition(AgentState.RECOVERY, task_id, f"Resource pressure: {reason}")
                    time.sleep(2.0)
                    can_proceed, reason = self.resource_governor.can_proceed_safely()
                    if not can_proceed:
                        # Halt task safely if critical pressure persists
                        fail_msg = f"Task paused/halted: system memory became critically low ({reason})."
                        self._terminate_task(task_id, False, fail_msg, turn_index)
                        return

                if self.resource_governor.should_throttle():
                    delays = self.resource_governor.get_recommended_delays()
                    time.sleep(delays["capture_delay_ms"] / 1000.0)

                # ==========================================
                # STAGE: OBSERVE
                # ==========================================
                self.state_engine.transition(AgentState.OBSERVE, task_id, f"Turn {turn_index}: Observing screen")
                self._current_step_activity = "Observing screen..."
                self.db.log_diagnostic("DEBUG", "AgentController", EVENT_OBSERVATION_CREATED, {
                    "turn_index": turn_index, "task_id": task_id
                })

                pre_state = self.screen_observer.observe(
                    force=False,
                    goal=goal,
                    last_interaction_pos=last_interaction_pos
                )

                # ==========================================
                # STAGE: REASON (Query Model / Local Planner)
                # ==========================================
                self.state_engine.transition(AgentState.REASON, task_id, f"Turn {turn_index}: Reasoning over observation")
                self._current_step_activity = "Analyzing current state..."
                self.db.log_diagnostic("DEBUG", "AgentController", EVENT_MODEL_REQUESTED, {
                    "observation_id": pre_state.observation_id
                })

                try:
                    proposal = self.model_manager.generate_action(
                        observation=pre_state,
                        goal=goal,
                        history=turn_history
                    )
                except Exception as e:
                    model_errors += 1
                    err_text = f"Model generation error: {str(e)}"
                    logger.warning("[Controller] %s", err_text)
                    if model_errors >= model_error_limit:
                        fail_msg = f"The local model is unavailable or returned repeated errors ({err_text})."
                        self._terminate_task(task_id, False, fail_msg, turn_index)
                        return
                    self.state_engine.transition(AgentState.RECOVERY, task_id, err_text)
                    time.sleep(0.5)
                    continue

                decision_summary = proposal.get("reason", "Executing planned action step.")
                proposed_action = proposal.get("action", {"type": "none"})
                verification_rule = proposal.get("verification", {"type": "screen_changed"})
                status = proposal.get("status", "CONTINUE")

                # Handle model ABORT status
                if status == "ABORT":
                    fail_msg = f"Agent aborted: {decision_summary}"
                    self._terminate_task(task_id, False, fail_msg, turn_index)
                    return

                # Detect repeated identical actions
                action_sig = f"{proposed_action.get('type')}:{proposed_action.get('node_id') or proposed_action.get('text')}"
                if action_sig == last_action_signature:
                    consecutive_same_action_count += 1
                else:
                    consecutive_same_action_count = 1
                    last_action_signature = action_sig

                if consecutive_same_action_count > same_action_failure_limit:
                    logger.warning("[Controller] Detected infinite action loop on '%s'; triggering recovery", action_sig)
                    self.state_engine.transition(AgentState.RECOVERY, task_id, "Repeated identical action loop prevented")
                    self.screen_observer.invalidate_cache()
                    consecutive_same_action_count = 0
                    time.sleep(0.5)
                    turn_index += 1
                    continue

                if self._cancel_requested:
                    break

                # ==========================================
                # STAGE: ACT (Validated Dispatch)
                # ==========================================
                if self._cancel_requested:
                    break
                self.state_engine.transition(AgentState.ACT, task_id, f"Turn {turn_index}: Dispatching {proposed_action.get('type')}")
                
                # Concise user activity message
                act_type = proposed_action.get("type", "none")
                if act_type in ("click_node", "double_click_node"):
                    target_node = pre_state.get_node(proposed_action.get("node_id", ""))
                    node_label = f'"{target_node.text}"' if target_node else "target element"
                    self._current_step_activity = f"Clicking {node_label}..."
                elif act_type == "type_text":
                    self._current_step_activity = "Entering text..."
                elif act_type == "wait":
                    self._current_step_activity = "Pacing execution..."
                else:
                    self._current_step_activity = f"Performing {act_type}..."

                action_result = self.action_executor.execute(proposed_action, pre_state)
                self.db.log_diagnostic("DEBUG", "AgentController", EVENT_ACTION_EXECUTED, {
                    "action_result": action_result
                })

                # Check action dispatch success
                if not action_result.get("success"):
                    action_failures += 1
                    action_err = action_result.get("error", "Unknown dispatch failure")
                    logger.warning("[Controller] Action rejected/failed: %s", action_err)

                    if action_failures >= same_action_failure_limit:
                        fail_msg = f"Action could not be executed: {action_err}"
                        self._terminate_task(task_id, False, fail_msg, turn_index)
                        return

                    self.state_engine.transition(AgentState.RECOVERY, task_id, f"Action failed: {action_err}")
                    self.screen_observer.invalidate_cache()
                    time.sleep(0.8)
                    turn_index += 1
                    continue

                # Update last interaction position for spatial OCR ranking
                if "clicked_at" in action_result.get("details", {}):
                    last_interaction_pos = action_result["details"]["clicked_at"]

                # ==========================================
                # STAGE: POST-ACTION OBSERVE & STATE DIFF
                # ==========================================
                if self._cancel_requested:
                    break
                self._current_step_activity = "Capturing resulting state..."
                post_state = self.screen_observer.observe(force=True, goal=goal, last_interaction_pos=last_interaction_pos)
                state_diff = self.screen_observer.get_last_diff() or {}

                # ==========================================
                # STAGE: VERIFY (Deterministic Evaluation)
                # ==========================================
                if self._cancel_requested:
                    break
                self.state_engine.transition(AgentState.VERIFY, task_id, f"Turn {turn_index}: Verifying action outcome")
                self._current_step_activity = "Verifying result..."

                v_passed, v_details, v_meta = self.verification_engine.verify_action_outcome(
                    rule=verification_rule,
                    prev_state=pre_state,
                    curr_state=post_state,
                    state_diff=state_diff
                )

                if v_passed:
                    self.db.log_diagnostic("INFO", "AgentController", EVENT_VERIFICATION_PASSED, {
                        "details": v_details
                    })
                    verification_failures = 0
                else:
                    verification_failures += 1
                    self.db.log_diagnostic("WARNING", "AgentController", EVENT_VERIFICATION_FAILED, {
                        "details": v_details, "fail_count": verification_failures
                    })
                    logger.warning("[Controller] Turn %d verification failed (%d/%d): %s",
                                   turn_index, verification_failures, verification_failure_limit, v_details)

                    if verification_failures >= verification_failure_limit:
                        fail_msg = "The action could not be verified within retry limits. Panther halted for safety."
                        self._terminate_task(task_id, False, fail_msg, turn_index)
                        return

                    self._current_step_activity = "Action outcome could not be verified; reconsidering current screen..."
                    self.state_engine.transition(AgentState.RECOVERY, task_id, f"Verification failed: {v_details}")
                    self.screen_observer.invalidate_cache()
                    time.sleep(0.5)

                # Record turn event in SQLite
                event_id = f"ev_{uuid.uuid4().hex[:8]}"
                self.db.record_task_event(
                    event_id=event_id,
                    task_id=task_id,
                    turn_index=turn_index,
                    state=self.state_engine.current_state,
                    proposal_summary=decision_summary,
                    action_type=proposed_action.get("type"),
                    action_params=proposed_action,
                    action_result=action_result,
                    verification_rule=verification_rule,
                    verification_passed=v_passed,
                    verification_details=v_details
                )

                turn_record = {
                    "turn_index": turn_index,
                    "observation_id": pre_state.observation_id,
                    "decision": decision_summary,
                    "action": proposed_action,
                    "result": action_result,
                    "verified": v_passed,
                    "diff": state_diff
                }
                turn_history.append(turn_record)

                # ==========================================
                # STAGE: GOAL CHECK (Deterministic Verifier)
                # ==========================================
                if self._cancel_requested:
                    break
                self.state_engine.transition(AgentState.GOAL_CHECK, task_id, f"Turn {turn_index}: Evaluating goal completion")
                self._current_step_activity = "Checking goal completion..."

                model_claimed_done = (status == "DONE")
                is_goal_achieved, goal_details = self.goal_verifier.evaluate_goal(
                    goal_spec=goal,
                    model_proposed_done=model_claimed_done,
                    curr_state=post_state,
                    state_diff=state_diff
                )

                if is_goal_achieved:
                    self.db.log_diagnostic("INFO", "AgentController", EVENT_GOAL_CHECK_PASSED, {
                        "goal_details": goal_details
                    })
                    self.state_engine.transition(AgentState.COMPLETE, task_id, goal_details)
                    self._current_step_activity = f"Goal reached: {goal_details}"
                    self.db.update_task_state(
                        task_id=task_id,
                        state=AgentState.COMPLETE,
                        success=True,
                        termination_reason=goal_details,
                        turns=turn_index + 1
                    )
                    self.db.log_diagnostic("INFO", "AgentController", EVENT_TASK_COMPLETED, {"task_id": task_id})
                    logger.info("[Controller] Task %s COMPLETED successfully in %d turns", task_id, turn_index + 1)
                    return
                else:
                    if model_claimed_done:
                        logger.warning("[Controller] Model claimed DONE but deterministic goal check was FALSE: %s", goal_details)
                        self._current_step_activity = "Model claimed goal complete, but verification criteria unmet. Continuing..."
                        self.state_engine.transition(AgentState.RECOVERY, task_id, "False model completion rejected")
                        time.sleep(0.5)

                turn_index += 1
                time.sleep(0.1)

            # Check if task was cancelled or finished
            if self._cancel_requested or self.state_engine.current_state in (AgentState.CANCELLED, AgentState.COMPLETE):
                return

            # Turn limit reached without verified completion
            term_msg = f"Task halted: reached turn limit ({max_turns}) without verified goal completion."
            self._terminate_task(task_id, False, term_msg, turn_index)

        except Exception as e:
            if not self._cancel_requested and self.state_engine.current_state != AgentState.CANCELLED:
                err_msg = f"Unhandled controller runtime exception: {str(e)}"
                logger.error(err_msg, exc_info=True)
                self._terminate_task(task_id, False, err_msg, turn_index)
        finally:
            with self._lock:
                self._active_task_id = None
                self._active_task_goal = None
                self._pause_requested = False
                self._cancel_requested = False

    def _terminate_task(self, task_id: str, success: bool, reason: str, turns: int):
        """Cleanly updates state and database upon task termination."""
        final_state = AgentState.COMPLETE if success else AgentState.FAILED
        self.state_engine.transition(final_state, task_id, reason)
        self._current_step_activity = reason
        self.db.update_task_state(
            task_id=task_id,
            state=final_state,
            success=success,
            termination_reason=reason,
            turns=turns
        )
        self.db.log_diagnostic(
            "INFO" if success else "ERROR",
            "AgentController",
            EVENT_TASK_COMPLETED if success else EVENT_TASK_FAILED,
            {"task_id": task_id, "reason": reason, "turns": turns}
        )
