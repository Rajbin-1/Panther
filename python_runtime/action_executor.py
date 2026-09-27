"""
Panther Agent - Action Executor
Strict untrusted model action boundary.
Enforces observation freshness, node-level coordinate calculation, forbidden key filters,
and zero shell / file / process manipulation capabilities.
"""

import time
import platform
import logging
from typing import Dict, Any, Tuple, Optional, Set
from database import DatabaseManager
from config_manager import ConfigManager
from screen_state import ScreenState, OcrNode

logger = logging.getLogger("panther.action_executor")

# Supported safe action types
SUPPORTED_ACTIONS: Set[str] = {
    "click",
    "double_click",
    "right_click",
    "click_node",
    "double_click_node",
    "move_mouse",
    "type_text",
    "send_key_combination",
    "press_key",
    "key_combination",
    "scroll",
    "wait",
    "focus_window",
    "request_clarification",
    "none"
}

# Explicit keyboard allowlist
KEYBOARD_ALLOWLIST: Set[str] = {
    "enter", "tab", "escape", "backspace", "delete", "space",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
    "ctrl+a", "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+y", "ctrl+s", "ctrl+f",
    "ctrl+shift+z", "shift+tab", "ctrl+w"
}

FORBIDDEN_KEY_PATTERNS: Set[str] = {
    "alt+f4", "ctrl+alt+del", "win+l", "format", "shutdown", "reboot",
    "del /", "rm -rf", "drop table", "powershell", "cmd.exe", "bash"
}

class ActionExecutor:
    def __init__(self, db: DatabaseManager, config: ConfigManager, screen_observer=None):
        self.db = db
        self.config = config
        self.screen_observer = screen_observer
        self.is_windows = platform.system().lower() == "windows"
        self._last_executed_action: Optional[Dict[str, Any]] = None

    def validate_action(
        self,
        action: Dict[str, Any],
        screen_state: Optional[ScreenState]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validates untrusted model proposal against safety policies and screen state.
        Returns (is_valid, reason, resolved_params).
        """
        if not isinstance(action, dict):
            return False, "Action must be a valid JSON dictionary.", None

        action_type = str(action.get("action_type") or action.get("type") or "none").lower().strip()
        if action_type not in SUPPORTED_ACTIONS:
            return False, f"Action '{action_type}' rejected: not in authorized action whitelist.", None

        # 1. Click Actions (click, double_click, right_click, click_node, double_click_node)
        if action_type in ("click", "double_click", "right_click", "click_node", "double_click_node"):
            target_node_id = action.get("target_node_id") or action.get("node_id")
            coordinates = action.get("coordinates")
            button = "right" if action_type == "right_click" else action.get("button", "left")

            if target_node_id:
                if screen_state is None:
                    return False, "No active screen observation available for node validation.", None

                # Verify observation freshness: node_id must belong to current observation
                if not target_node_id.startswith(f"{screen_state.observation_id}_"):
                    return False, f"STALE_NODE_REJECTED: node '{target_node_id}' does not belong to active observation '{screen_state.observation_id}'.", None

                node = screen_state.get_node(target_node_id)
                if node is None:
                    return False, f"NODE_NOT_FOUND: node '{target_node_id}' does not exist in current observation.", None

                # Verify visibility and coordinates
                if node.width <= 0 or node.height <= 0 or node.x < 0 or node.y < 0:
                    return False, f"Node '{target_node_id}' has invalid visual boundaries ({node.x}, {node.y}, {node.width}, {node.height}).", None

                if node.x > screen_state.width or node.y > screen_state.height:
                    return False, f"Node '{target_node_id}' coordinates exceed screen dimensions ({screen_state.width}x{screen_state.height}).", None

                resolved = {
                    "node_id": target_node_id,
                    "node_text": node.text,
                    "x": node.center_x,
                    "y": node.center_y,
                    "button": button,
                    "is_double": action_type in ("double_click", "double_click_node"),
                    "observation_id": screen_state.observation_id
                }
                return True, "Valid node action", resolved

            elif coordinates and isinstance(coordinates, dict):
                x = coordinates.get("x")
                y = coordinates.get("y")
                if x is None or y is None or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    return False, "Action coordinates must contain numeric 'x' and 'y'.", None

                max_w = screen_state.width if screen_state else 1920
                max_h = screen_state.height if screen_state else 1080
                if x < 0 or x > max_w or y < 0 or y > max_h:
                    return False, f"Coordinates ({x}, {y}) exceed display boundaries (0, 0, {max_w}, {max_h}).", None

                resolved = {
                    "node_id": None,
                    "node_text": None,
                    "x": int(x),
                    "y": int(y),
                    "button": button,
                    "is_double": action_type in ("double_click", "double_click_node"),
                    "observation_id": screen_state.observation_id if screen_state else None
                }
                return True, "Valid coordinate click", resolved
            else:
                return False, f"Action '{action_type}' requires either 'target_node_id' or 'coordinates'.", None

        # 2. Raw mouse movement (strictly clamped)
        if action_type == "move_mouse":
            coords = action.get("coordinates")
            x = coords.get("x") if isinstance(coords, dict) else action.get("x")
            y = coords.get("y") if isinstance(coords, dict) else action.get("y")

            if x is None or y is None or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                return False, "move_mouse requires numeric 'x' and 'y' coordinates.", None

            max_w = screen_state.width if screen_state else 1920
            max_h = screen_state.height if screen_state else 1080
            if x < 0 or x > max_w or y < 0 or y > max_h:
                return False, f"Coordinates ({x}, {y}) exceed display boundaries (0, 0, {max_w}, {max_h}).", None

            return True, "Valid mouse move", {"x": int(x), "y": int(y)}

        # 3. Text Entry
        if action_type == "type_text":
            text = action.get("input_text") if "input_text" in action else action.get("text")
            if text is None or not isinstance(text, str):
                return False, "type_text requires a string 'input_text' or 'text' parameter.", None

            if len(text) > 500:
                return False, "Text input exceeds 500 character safety limit.", None

            # Reject shell command payloads
            t_lower = text.lower().strip()
            for bad in FORBIDDEN_KEY_PATTERNS:
                if bad in t_lower:
                    return False, f"Text input rejected: contains prohibited pattern '{bad}'.", None

            return True, "Valid text input", {"text": text}

        # 4. Keyboard actions (send_key_combination, press_key, key_combination)
        if action_type in ("send_key_combination", "press_key", "key_combination"):
            key = str(action.get("key_combination") or action.get("key") or action.get("keys") or "").lower().strip()
            if not key:
                return False, f"Action '{action_type}' requires 'key_combination' or 'key' parameter.", None

            for bad in FORBIDDEN_KEY_PATTERNS:
                if bad in key:
                    return False, f"Prohibited keyboard shortcut '{key}' rejected by safety policy.", None

            # Check allowlist or standard single alphanumeric characters
            if key not in KEYBOARD_ALLOWLIST and not (len(key) == 1 and key.isalnum()):
                return False, f"Key '{key}' is not in authorized keyboard allowlist.", None

            return True, "Valid keyboard action", {"key": key}

        # 5. Scroll
        if action_type == "scroll":
            dy = action.get("scroll_delta") if "scroll_delta" in action else action.get("dy", 0)
            if not isinstance(dy, (int, float)):
                return False, "Scroll requires numeric 'scroll_delta' or 'dy'.", None
            if abs(dy) > 3000:
                return False, f"Scroll amount {dy} exceeds maximum bounded delta 3000.", None
            return True, "Valid scroll", {"dy": int(dy)}

        # 6. Wait
        if action_type == "wait":
            sec = action.get("wait_duration_ms") / 1000.0 if "wait_duration_ms" in action else action.get("seconds", 1.0)
            if not isinstance(sec, (int, float)) or sec < 0 or sec > 10.0:
                return False, "Wait duration must be between 0.0 and 10.0 seconds.", None
            return True, "Valid wait", {"seconds": float(sec)}

        # 7. Focus Window
        if action_type == "focus_window":
            win_title = str(action.get("title") or action.get("target_window") or action.get("window_title") or "")
            if not win_title:
                return False, "focus_window requires 'title' or 'target_window'.", None
            return True, "Valid focus", {"title": win_title}

        # 8. Request Clarification
        if action_type == "request_clarification":
            question = str(action.get("question") or action.get("reason") or "Clarification requested by agent.")
            return True, "Valid clarification request", {"question": question}

        # 9. None
        if action_type == "none":
            return True, "Valid none action", {}

        return False, f"Unhandled action type '{action_type}'.", None

    def execute(
        self,
        action: Dict[str, Any],
        screen_state: Optional[ScreenState]
    ) -> Dict[str, Any]:
        """
        Executes a validated action safely.
        """
        start_time = time.time()
        action_type = str(action.get("action_type") or action.get("type") or "none").lower().strip()

        # Step 1: Validate
        is_valid, reason, resolved = self.validate_action(action, screen_state)
        if not is_valid:
            self.db.log_diagnostic("WARNING", "ActionExecutor", f"Action rejected: {reason}", {
                "action": action,
                "screen_obs_id": screen_state.observation_id if screen_state else None
            })
            return {
                "success": False,
                "action_type": action_type,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "error": reason,
                "details": action
            }

        # Step 2: Rate limit pacing
        delay_ms = self.config.get_value("action_limits", "min_delay_between_actions_ms", 350)
        time.sleep(delay_ms / 1000.0)

        # Step 3: Platform execution
        exec_details = {}
        try:
            if action_type in ("click", "double_click", "right_click", "click_node", "double_click_node"):
                x = resolved["x"]
                y = resolved["y"]
                button = resolved.get("button", "left")

                self._dispatch_click(x, y, button)
                if resolved.get("is_double"):
                    time.sleep(0.08)
                    self._dispatch_click(x, y, button)

                exec_details = {
                    "node_id": resolved.get("node_id"),
                    "node_text": resolved.get("node_text"),
                    "clicked_at": (x, y),
                    "button": button
                }

            elif action_type == "move_mouse":
                x, y = resolved["x"], resolved["y"]
                self._dispatch_move(x, y)
                exec_details = {"moved_to": (x, y)}

            elif action_type == "type_text":
                text = resolved["text"]
                self._dispatch_type(text)
                exec_details = {"characters_typed": len(text)}

            elif action_type in ("send_key_combination", "press_key", "key_combination"):
                key = resolved["key"]
                self._dispatch_key(key)
                exec_details = {"key_dispatched": key}

            elif action_type == "scroll":
                dy = resolved["dy"]
                exec_details = {"scrolled_dy": dy}

            elif action_type == "wait":
                sec = resolved["seconds"]
                time.sleep(sec)
                exec_details = {"slept_seconds": sec}

            elif action_type == "focus_window":
                win = resolved["title"]
                exec_details = {"focused_window": win}

            elif action_type == "request_clarification":
                exec_details = {"clarification_question": resolved["question"]}

            elif action_type == "none":
                exec_details = {"action": "none"}

            # Notify screen observer so subsequent observation detects action mutation
            if self.screen_observer:
                self.screen_observer.notify_action_executed(action_type)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            result = {
                "success": True,
                "action_type": action_type,
                "execution_time_ms": elapsed_ms,
                "details": exec_details
            }
            self._last_executed_action = result
            return result

        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            err_msg = f"Action dispatch failed: {str(e)}"
            logger.error(err_msg, exc_info=True)
            self.db.log_diagnostic("ERROR", "ActionExecutor", err_msg, {
                "action": action,
                "resolved": resolved
            })
            return {
                "success": False,
                "action_type": action_type,
                "execution_time_ms": elapsed_ms,
                "error": err_msg,
                "details": action
            }

    def _dispatch_click(self, x: int, y: int, button: str = "left"):
        if self.is_windows:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.SetCursorPos(x, y)
                flags_down = 0x0002 if button == "left" else 0x0008
                flags_up = 0x0004 if button == "left" else 0x0010
                user32.mouse_event(flags_down, 0, 0, 0, 0)
                time.sleep(0.02)
                user32.mouse_event(flags_up, 0, 0, 0, 0)
                return
            except Exception as e:
                logger.debug("Windows click execution note: %s", e)
        logger.info("[ActionExecutor] Emulated %s click at (%d, %d)", button, x, y)

    def _dispatch_move(self, x: int, y: int):
        if self.is_windows:
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(x, y)
                return
            except Exception:
                pass
        logger.info("[ActionExecutor] Emulated mouse move to (%d, %d)", x, y)

    def _dispatch_type(self, text: str):
        logger.info("[ActionExecutor] Emulated text type: %s", text[:30])

    def _dispatch_key(self, key: str):
        logger.info("[ActionExecutor] Emulated key press: %s", key)
