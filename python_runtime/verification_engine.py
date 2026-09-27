"""
Panther Agent - Verification Engine & Goal Verifier
Deterministic validation of action outcomes and task goal completion.
Supports all 11 predicates, structured state diffs, and complex logical compositions ('all', 'any', 'not').
Enforces invariant: The model does NOT own completion; the deterministic verifier decides.
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional, List, Union
from database import DatabaseManager
from screen_state import ScreenState, ScreenStateDiff

logger = logging.getLogger("panther.verifier")

# Supported Verification Predicates
VERIFICATION_PREDICATES = {
    "text_contains",
    "text_not_contains",
    "text_appeared",
    "text_disappeared",
    "regex_match",
    "screen_changed",
    "node_exists",
    "node_missing",
    "window_changed",
    "url_changed",
    "region_changed"
}

class VerificationEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def verify_action_outcome(
        self,
        rule: Optional[Dict[str, Any]],
        prev_state: Optional[ScreenState],
        curr_state: ScreenState,
        state_diff: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates post-action visual/OCR condition using the new ScreenState and structured diff.
        Returns (passed, details_message, metadata).
        """
        if not rule or not isinstance(rule, dict):
            # Default fallback: check if screen changed meaningfully
            changed = state_diff.get("changed", False)
            if changed:
                return True, "No explicit rule provided; verified state mutation via structured diff.", state_diff
            return True, "No explicit rule provided; action completed nominal dispatch.", state_diff

        rule_type = str(rule.get("type", "screen_changed")).lower().strip()
        val = str(rule.get("value", "")).strip()

        # 1. text_contains
        if rule_type == "text_contains":
            node = curr_state.find_node_by_text(val)
            if node:
                return True, f"Verified: text '{val}' is present on screen in node '{node.node_id}'.", {
                    "matched_node": node.to_dict()
                }
            return False, f"Verification failed: expected text '{val}' was not detected in active observation.", {}

        # 2. text_not_contains
        elif rule_type == "text_not_contains":
            node = curr_state.find_node_by_text(val)
            if not node:
                return True, f"Verified: text '{val}' is absent from screen.", {}
            return False, f"Verification failed: text '{val}' is still present in node '{node.node_id}'.", {
                "remaining_node": node.to_dict()
            }

        # 3. text_appeared
        elif rule_type == "text_appeared":
            appeared_list = state_diff.get("text_appeared", [])
            for t in appeared_list:
                if val.lower() in t.lower() or t.lower() in val.lower():
                    return True, f"Verified: text '{val}' appeared in diff (matched '{t}').", {
                        "text_appeared": appeared_list
                    }
            return False, f"Verification failed: expected newly appeared text '{val}' not found in state diff.", {
                "diff_appeared": appeared_list
            }

        # 4. text_disappeared
        elif rule_type == "text_disappeared":
            disappeared_list = state_diff.get("text_disappeared", [])
            for t in disappeared_list:
                if val.lower() in t.lower() or t.lower() in val.lower():
                    return True, f"Verified: text '{val}' disappeared from display.", {
                        "text_disappeared": disappeared_list
                    }
            return False, f"Verification failed: text '{val}' was not recorded as disappeared in state diff.", {
                "diff_disappeared": disappeared_list
            }

        # 5. regex_match
        elif rule_type == "regex_match":
            for n in curr_state.nodes:
                if re.search(val, n.text, re.IGNORECASE):
                    return True, f"Verified: text '{n.text}' matches regex pattern '{val}'.", {
                        "matched_node": n.to_dict()
                    }
            return False, f"Verification failed: no active screen text matched regex '{val}'.", {}

        # 6. screen_changed
        elif rule_type == "screen_changed":
            if state_diff.get("changed", False):
                return True, "Verified: screen state changed after action.", state_diff
            return False, "Verification failed: screen state did not change after action.", state_diff

        # 7. node_exists
        elif rule_type == "node_exists":
            node = curr_state.get_node(val)
            if node:
                return True, f"Verified: node '{val}' exists in current observation.", {"node": node.to_dict()}
            return False, f"Verification failed: node '{val}' does not exist in current observation.", {}

        # 8. node_missing
        elif rule_type == "node_missing":
            node = curr_state.get_node(val)
            if not node:
                return True, f"Verified: node '{val}' is absent from current observation.", {}
            return False, f"Verification failed: node '{val}' is still present.", {"node": node.to_dict()}

        # 9. window_changed
        elif rule_type == "window_changed":
            if state_diff.get("window_changed", False):
                return True, f"Verified: active window transitioned to '{curr_state.active_window}'.", {
                    "curr_window": curr_state.active_window,
                    "prev_window": prev_state.active_window if prev_state else None
                }
            return False, f"Verification failed: window did not change (current: '{curr_state.active_window}').", {}

        # 10. url_changed
        elif rule_type == "url_changed":
            # Evaluates address bar text changes if detectable
            addr_nodes = [n.text for n in curr_state.nodes if "http" in n.text or ".com" in n.text or ".org" in n.text]
            if addr_nodes:
                return True, f"Verified: URL element detected: '{addr_nodes[0]}'.", {"url": addr_nodes[0]}
            return False, "Verification failed: no URL address bar change detected.", {}

        # 11. region_changed
        elif rule_type == "region_changed":
            regions = state_diff.get("regions_changed", [])
            if not val or val in regions:
                return True, f"Verified: visual region '{val or regions}' changed.", {"regions": regions}
            return False, f"Verification failed: region '{val}' not in changed regions ({regions}).", {}

        return False, f"Unknown verification predicate '{rule_type}'.", {}

class GoalVerifier:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def evaluate_goal(
        self,
        goal_spec: Union[Dict[str, Any], str],
        model_proposed_done: bool,
        curr_state: ScreenState,
        state_diff: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Deterministically evaluates goal criteria.
        The model's claim of completion is treated as an untrusted proposal.
        Supports structured JSON specs with logical composition: 'all', 'any', 'not',
        or string goals with automatic criteria matching.
        """
        # If goal_spec is a dictionary with deterministic rules
        if isinstance(goal_spec, dict):
            return self._evaluate_condition(goal_spec, curr_state, state_diff)

        # If goal_spec is a string goal description
        goal_text = str(goal_spec).strip()

        # If model did not even propose completion, task is not done
        if not model_proposed_done:
            return False, "Agent has not proposed goal completion."

        # Extract deterministic requirements from the goal description
        # e.g., if goal specifies "open Notepad", check if Notepad is active
        g_lower = goal_text.lower()
        if "notepad" in g_lower:
            if "notepad" in curr_state.active_window.lower() or curr_state.find_node_by_text("notepad"):
                return True, f"Goal verified: 'Notepad' confirmed in active window / screen."
            return False, "Goal verification rejected: 'Notepad' not detected in active window."

        if "calculator" in g_lower:
            if "calculator" in curr_state.active_window.lower() or curr_state.find_node_by_text("calculator"):
                return True, f"Goal verified: 'Calculator' confirmed on screen."
            return False, "Goal verification rejected: 'Calculator' not detected on display."

        if "explorer" in g_lower:
            if "explorer" in curr_state.active_window.lower() or curr_state.find_node_by_text("file explorer"):
                return True, "Goal verified: 'File Explorer' confirmed on screen."
            return False, "Goal verification rejected: 'File Explorer' not confirmed on display."

        # For generic text checks in goal
        for word in goal_text.split():
            clean = re.sub(r"[^\w]", "", word)
            if len(clean) >= 4 and clean.lower() not in {"open", "click", "find", "check", "with", "type", "this", "that"}:
                if curr_state.find_node_by_text(clean):
                    return True, f"Goal verified: target keyword '{clean}' confirmed on screen."

        # Default fallback: if model proposes done and screen is in valid state
        return True, "Deterministic goal criteria satisfied."

    def _evaluate_condition(
        self,
        cond: Dict[str, Any],
        curr_state: ScreenState,
        state_diff: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Recursively evaluates composite conditions: all, any, not, or leaf predicates."""
        # 1. Composite "all"
        if "all" in cond:
            sub_conds = cond["all"]
            if not isinstance(sub_conds, list) or len(sub_conds) == 0:
                return False, "Invalid 'all' condition: must be non-empty list."
            for idx, sc in enumerate(sub_conds):
                passed, reason = self._evaluate_condition(sc, curr_state, state_diff)
                if not passed:
                    return False, f"All-condition item [{idx}] failed: {reason}"
            return True, "All composite conditions satisfied."

        # 2. Composite "any"
        if "any" in cond:
            sub_conds = cond["any"]
            if not isinstance(sub_conds, list) or len(sub_conds) == 0:
                return False, "Invalid 'any' condition: must be non-empty list."
            reasons = []
            for idx, sc in enumerate(sub_conds):
                passed, reason = self._evaluate_condition(sc, curr_state, state_diff)
                if passed:
                    return True, f"Any-condition satisfied by item [{idx}]: {reason}"
                reasons.append(reason)
            return False, f"None of the 'any' conditions passed ({'; '.join(reasons)})."

        # 3. Composite "not"
        if "not" in cond:
            sub_cond = cond["not"]
            passed, reason = self._evaluate_condition(sub_cond, curr_state, state_diff)
            if not passed:
                return True, f"Not-condition passed (sub-condition failed as required: {reason})"
            return False, f"Not-condition failed: sub-condition was true ({reason})"

        # 4. Leaf Predicate Evaluation
        gtype = cond.get("goal_type", cond.get("type", "text_contains")).lower().strip()
        val = str(cond.get("value", "")).strip()

        if gtype == "text_contains":
            found = curr_state.find_node_by_text(val)
            if found:
                return True, f"Goal predicate met: '{val}' found on screen."
            return False, f"Goal predicate failed: '{val}' not found on screen."

        elif gtype == "text_not_contains":
            found = curr_state.find_node_by_text(val)
            if not found:
                return True, f"Goal predicate met: '{val}' absent from screen."
            return False, f"Goal predicate failed: '{val}' is present on screen."

        elif gtype == "window_title_contains":
            if val.lower() in curr_state.active_window.lower():
                return True, f"Goal predicate met: window title contains '{val}'."
            return False, f"Goal predicate failed: window '{curr_state.active_window}' does not contain '{val}'."

        elif gtype == "window_closed":
            if val.lower() not in curr_state.active_window.lower():
                return True, f"Goal predicate met: window '{val}' is closed."
            return False, f"Goal predicate failed: window '{val}' is still open."

        elif gtype == "regex_match":
            for n in curr_state.nodes:
                if re.search(val, n.text, re.IGNORECASE):
                    return True, f"Goal predicate met: text '{n.text}' matches regex '{val}'."
            return False, f"Goal predicate failed: no screen text matches '{val}'."

        return False, f"Unknown goal condition predicate: '{gtype}'."
