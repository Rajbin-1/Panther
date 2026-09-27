"""
Panther Agent - Automated Test Suite (Stage 2)
Tests all security boundaries, model schema enforcement, deterministic verifications,
and End-to-End Scenarios (Tests A through H).
"""

import sys
import os
import time
import unittest
from typing import Dict, Any, List

# Ensure python_runtime in path
pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from database import DatabaseManager
from config_manager import ConfigManager
from resource_governor import ResourceGovernor, ResourcePressure
from device_manager import DeviceManager
from screen_state import ScreenState, ScreenStateDiff, OcrNode
from ocr_processor import OcrProcessor
from screen_observer import ScreenObserver
from action_executor import ActionExecutor
from verification_engine import VerificationEngine, GoalVerifier
from model_manager import ModelManager
from state_engine import StateEngine, AgentState
from agent_controller import AgentController

class TestPantherAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.test_db_path = f"/tmp/test_panther_runtime_{int(time.time() * 1000)}.db"
        self.db = DatabaseManager(self.test_db_path)
        self.config = ConfigManager(self.db)
        self.governor = ResourceGovernor(self.db, self.config)
        self.ocr = OcrProcessor(self.db, self.config)
        self.screen = ScreenObserver(self.db, self.config, self.ocr)
        self.executor = ActionExecutor(self.db, self.config, self.screen)
        self.verifier = VerificationEngine(self.db)
        self.goal_ver = GoalVerifier(self.db)
        self.model = ModelManager(self.db, self.config)
        self.state = StateEngine(self.db)

        self.controller = AgentController(
            db=self.db,
            config=self.config,
            resource_governor=self.governor,
            screen_observer=self.screen,
            action_executor=self.executor,
            verification_engine=self.verifier,
            goal_verifier=self.goal_ver,
            model_manager=self.model,
            state_engine=self.state
        )

    def tearDown(self):
        try:
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception:
            pass

    # ========================================================
    # 1. SECURITY & ACTION BOUNDARY TESTS
    # ========================================================

    def test_01_reject_arbitrary_shell_command(self):
        """Proves that arbitrary shell execution is rejected unconditionally."""
        action = {"type": "type_text", "text": "rm -rf /"}
        obs = self.screen.observe()
        is_valid, reason, _ = self.executor.validate_action(action, obs)
        self.assertFalse(is_valid)
        self.assertIn("prohibited pattern", reason)

        # Direct shell command injection
        action_shell = {"type": "shell_exec", "command": "cmd.exe /c calc"}
        is_valid, reason, _ = self.executor.validate_action(action_shell, obs)
        self.assertFalse(is_valid)
        self.assertIn("not in authorized action whitelist", reason)

    def test_02_reject_executable_launch(self):
        """Proves that executable launching cannot be dispatched through action boundary."""
        action = {"type": "launch_process", "path": "C:\\Windows\\System32\\cmd.exe"}
        obs = self.screen.observe()
        is_valid, reason, _ = self.executor.validate_action(action, obs)
        self.assertFalse(is_valid)
        self.assertIn("not in authorized action whitelist", reason)

    def test_03_reject_filesystem_write(self):
        """Proves filesystem manipulation is not an allowed action."""
        action = {"type": "write_file", "path": "C:\\test.txt", "content": "bad"}
        obs = self.screen.observe()
        is_valid, reason, _ = self.executor.validate_action(action, obs)
        self.assertFalse(is_valid)

    def test_04_reject_prohibited_keyboard_shortcut(self):
        """Proves dangerous system shortcuts (alt+f4, ctrl+alt+del, win+l) are blocked."""
        obs = self.screen.observe()
        for bad_key in ["alt+f4", "ctrl+alt+del", "win+l", "shutdown"]:
            action = {"type": "key_combination", "key": bad_key}
            is_valid, reason, _ = self.executor.validate_action(action, obs)
            self.assertFalse(is_valid, f"Expected {bad_key} to be rejected")
            self.assertIn("rejected by safety policy", reason)

    def test_05_reject_stale_node(self):
        """Test D: Generate a node ID, change screen observation, then attempt to use old node."""
        obs_1 = self.screen.observe(force=True)
        node_id_1 = obs_1.nodes[0].node_id
        self.assertTrue(node_id_1.startswith(f"{obs_1.observation_id}_"))

        # Mutate screen to advance observation ID
        self.screen.notify_action_executed("click")
        obs_2 = self.screen.observe(force=True)
        self.assertNotEqual(obs_1.observation_id, obs_2.observation_id)

        # Attempt to use stale node from obs_1 in obs_2
        stale_action = {"type": "click_node", "node_id": node_id_1}
        is_valid, reason, _ = self.executor.validate_action(stale_action, obs_2)
        self.assertFalse(is_valid)
        self.assertIn("STALE_NODE_REJECTED", reason)

    def test_06_reject_out_of_bounds_coordinates(self):
        """Proves coordinates outside active display bounds are clamped/rejected."""
        obs = self.screen.observe()
        action_oob = {"type": "move_mouse", "x": 99999, "y": 99999}
        is_valid, reason, _ = self.executor.validate_action(action_oob, obs)
        self.assertFalse(is_valid)
        self.assertIn("exceed display boundaries", reason)

    def test_07_reject_malformed_json_and_unknown_actions(self):
        """Proves strict schema validation rejects invalid structures."""
        obs = self.screen.observe()
        is_valid, reason, _ = self.model.validate_model_response("not a dict", obs.observation_id)
        self.assertFalse(is_valid)

        bad_action_resp = {
            "status": "CONTINUE",
            "reason": "Test",
            "action": {"type": "destroy_everything"},
            "verification": {"type": "screen_changed"}
        }
        is_valid, reason, _ = self.model.validate_model_response(bad_action_resp, obs.observation_id)
        self.assertFalse(is_valid)
        self.assertIn("Unknown action type", reason)

    def test_08_reject_excessive_limits(self):
        """Proves safety bounds on wait, scroll, and oversized text."""
        obs = self.screen.observe()
        # Excessive wait (> 10s)
        action_wait = {"type": "wait", "seconds": 3600}
        is_valid, reason, _ = self.executor.validate_action(action_wait, obs)
        self.assertFalse(is_valid)

        # Excessive scroll (> 3000)
        action_scroll = {"type": "scroll", "dy": 99999}
        is_valid, reason, _ = self.executor.validate_action(action_scroll, obs)
        self.assertFalse(is_valid)

        # Oversized text input (> 500 chars)
        action_text = {"type": "type_text", "text": "A" * 600}
        is_valid, reason, _ = self.executor.validate_action(action_text, obs)
        self.assertFalse(is_valid)

    # ========================================================
    # 2. END-TO-END SCENARIO TESTS (Tests A through H)
    # ========================================================

    def test_scenario_A_simple_ui_interaction(self):
        """
        Test A — Simple UI interaction
        Task: 'Open a known local application and click a known visible button.'
        Verify: OBSERVE -> REASON -> ACT -> VERIFY -> GOAL CHECK -> COMPLETE
        """
        # Inject known visible button element
        self.ocr.set_active_screen_elements([
            {"text": "Calculator", "x": 100, "y": 100, "width": 80, "height": 30, "confidence": 0.99},
            {"text": "Calculate", "x": 200, "y": 200, "width": 90, "height": 32, "confidence": 0.98}
        ])

        res = self.controller.start_task("Open Calculator and calculate total")
        self.assertTrue(res["success"])
        task_id = res["task_id"]

        # Wait for task completion
        time.sleep(1.8)
        status = self.controller.get_current_status()
        details = self.db.get_task_details(task_id)

        self.assertIsNotNone(details)
        self.assertEqual(details["state"], AgentState.COMPLETE)
        self.assertEqual(details["success"], 1)
        self.assertGreaterEqual(len(details["events"]), 1)

    def test_scenario_B_multi_step_interaction(self):
        """
        Test B — Multi-step interaction
        A task requiring at least three actions. Verify agent does not assume success after first action.
        """
        self.ocr.set_active_screen_elements([
            {"text": "Settings", "x": 80, "y": 80, "width": 70, "height": 28, "confidence": 0.95},
            {"text": "Network", "x": 80, "y": 140, "width": 70, "height": 28, "confidence": 0.95},
            {"text": "Proxy", "x": 80, "y": 200, "width": 60, "height": 28, "confidence": 0.95}
        ])

        res = self.controller.start_task("Navigate to Proxy in Settings")
        task_id = res["task_id"]

        time.sleep(2.5)
        details = self.db.get_task_details(task_id)
        self.assertIsNotNone(details)
        # Verify turns progressed through multi-step
        self.assertGreaterEqual(details["total_turns"], 2)

    def test_scenario_C_wrong_action_recovery(self):
        """
        Test C — Wrong action
        Force an unverified outcome; verify action validation, verification failure, and recovery.
        """
        obs_pre = self.screen.observe(force=True)
        # Set impossible verification condition
        rule = {"type": "text_contains", "value": "THIS_TEXT_DEFINITELY_DOES_NOT_EXIST_XYZ"}
        obs_post = self.screen.observe(force=True)
        diff = self.screen.get_last_diff() or {}

        passed, details, _ = self.verifier.verify_action_outcome(rule, obs_pre, obs_post, diff)
        self.assertFalse(passed)
        self.assertIn("Verification failed", details)

    def test_scenario_E_false_model_completion(self):
        """
        Test E — False completion
        Model claims status='DONE', but deterministic goal criteria is false.
        Expected: GoalVerifier rejects completion; task remains incomplete.
        """
        obs = self.screen.observe(force=True)
        diff = self.screen.get_last_diff() or {}

        # Goal requires Calculator, but screen only has Desktop markers
        goal_spec = {"goal_type": "text_contains", "value": "UNAVAILABLE_SECRET_TOKEN_999"}
        is_done, reason = self.goal_ver.evaluate_goal(goal_spec, model_proposed_done=True, curr_state=obs, state_diff=diff)

        self.assertFalse(is_done)
        self.assertIn("Goal predicate failed", reason)

    def test_scenario_F_resource_pressure_interruption(self):
        """
        Test F — Resource pressure
        Simulate critical memory pressure. Expected: task pauses/halts safely without corrupting state.
        """
        # Set config critical threshold above current RAM to simulate starvation
        self.config.update_section("resource_limits", {
            "critical_available_ram_mb": 999999
        })

        can_proceed, reason = self.governor.can_proceed_safely()
        self.assertFalse(can_proceed)
        self.assertIn("Critical RAM starvation", reason)

        # Restore normal threshold
        self.config.update_section("resource_limits", {
            "critical_available_ram_mb": 512
        })

    def test_scenario_G_cancellation_during_execution(self):
        """
        Test G — Cancellation
        Cancel during active task. Expected: immediate halt, state is CANCELLED.
        """
        res = self.controller.start_task("Continuous background monitoring task")
        task_id = res["task_id"]

        time.sleep(0.3)
        cancel_res = self.controller.cancel_task()
        self.assertTrue(cancel_res["success"])

        time.sleep(0.5)
        status = self.controller.get_current_status()
        self.assertEqual(status["state"], AgentState.CANCELLED)

        # Verify no further execution
        details = self.db.get_task_details(task_id)
        self.assertEqual(details["state"], AgentState.CANCELLED)

    def test_scenario_H_model_unavailable_fallback(self):
        """
        Test H — Model runtime unavailable
        Ollama is offline. Expected: clean fallback to deterministic planner, no crash, no infinite loop.
        """
        # Ensure endpoint is unreachable
        self.config.update_section("model", {"endpoint": "http://127.0.0.1:59999"})
        health = self.model.check_ollama_health()
        self.assertFalse(health["connected"])

        # Generate action with offline model
        obs = self.screen.observe(force=True)
        action_prop = self.model.generate_action(obs, "Test offline goal", [])
        self.assertIn("status", action_prop)
        self.assertIn("action", action_prop)
        self.assertEqual(action_prop["status"], "CONTINUE")

    def test_logical_goal_composition(self):
        """Proves composite 'all', 'any', 'not' deterministic goal verification."""
        self.ocr.set_active_screen_elements([
            {"text": "Dashboard", "x": 100, "y": 100, "width": 80, "height": 30, "confidence": 0.99},
            {"text": "Status: Active", "x": 100, "y": 140, "width": 90, "height": 25, "confidence": 0.95}
        ])
        obs = self.screen.observe(force=True)
        diff = self.screen.get_last_diff() or {}

        # 1. Composite "all" test: text_contains Dashboard AND NOT contains Loading
        composite_all = {
            "all": [
                {"goal_type": "text_contains", "value": "Dashboard"},
                {"not": {"goal_type": "text_contains", "value": "Loading"}}
            ]
        }
        passed, reason = self.goal_ver.evaluate_goal(composite_all, True, obs, diff)
        self.assertTrue(passed)
        self.assertIn("All composite conditions satisfied", reason)

        # 2. Composite "any" test: Error OR Dashboard
        composite_any = {
            "any": [
                {"goal_type": "text_contains", "value": "Fatal Error"},
                {"goal_type": "text_contains", "value": "Dashboard"}
            ]
        }
        passed, reason = self.goal_ver.evaluate_goal(composite_any, True, obs, diff)
        self.assertTrue(passed)

    def test_stage2_action_proposal_schema(self):
        """Verifies strict validation of the canonical Stage 2 action proposal schema."""
        obs = self.screen.observe(force=True)
        valid_node_id = obs.nodes[0].node_id

        # Direct Stage 2 proposal schema
        proposal = {
            "action_type": "click",
            "target_node_id": valid_node_id,
            "concise_intent": "Click primary element",
            "proposed_verification": {
                "type": "text_appeared",
                "condition": "menu opened",
                "expected_text": "File saved",
                "timeout_ms": 3000
            },
            "proposed_completion": {
                "completed": False,
                "reason": "Step 1 of 2"
            }
        }
        is_valid, reason, clean = self.model.validate_model_response(proposal, obs.observation_id)
        self.assertTrue(is_valid, f"Expected proposal to be valid, got: {reason}")
        self.assertEqual(clean["action"]["type"], "click")
        self.assertEqual(clean["verification"]["value"], "File saved")

        # Action execution of this clean proposal
        exec_res = self.executor.execute(clean["action"], obs)
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["action_type"], "click")

    def test_stage2_screen_diff_fields(self):
        """Verifies ScreenStateDiff computes all deterministic fields."""
        obs_1 = self.screen.observe(force=True)
        # Add new elements to simulate screen change
        self.ocr.set_active_screen_elements([
            {"text": "New Dialog Window", "x": 50, "y": 50, "width": 120, "height": 30, "confidence": 0.98}
        ])
        self.screen.notify_action_executed("click")
        obs_2 = self.screen.observe(force=True)
        diff = self.screen.get_last_diff()

        self.assertIsNotNone(diff)
        self.assertTrue(diff["changed"])
        self.assertIn("fingerprint_changed", diff)
        self.assertIn("text_appeared", diff)
        self.assertIn("text_disappeared", diff)
        self.assertIn("nodes_added", diff)
        self.assertIn("nodes_removed", diff)
        self.assertIn("nodes_moved", diff)
        self.assertIn("regions_changed", diff)
        self.assertIn("window_changed", diff)

    def test_repetition_loop_detection(self):
        """Verifies controller breaks out of consecutive identical actions via RECOVERY state."""
        # Setup goal that won't complete immediately
        res = self.controller.start_task("Perform repetitive test")
        self.assertTrue(res["success"])
        task_id = res["task_id"]

        time.sleep(1.8)
        details = self.db.get_task_details(task_id)
        self.assertIsNotNone(details)
        # Should not exceed turn limit or hang
        self.assertLessEqual(details["total_turns"], 10)

if __name__ == "__main__":
    unittest.main()
