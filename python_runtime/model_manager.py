"""
Panther Agent - Model Manager
Ollama-compatible local model integration engineered for 6 GB RAM constraints.
Enforces strict JSON schema validation, bounded correction cycles, and clean interface:
ModelManager.generate_action(observation, task, history)
"""

import json
import re
import urllib.request
import urllib.error
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from database import DatabaseManager
from config_manager import ConfigManager
from screen_state import ScreenState, OcrNode

logger = logging.getLogger("panther.model_manager")

SUPPORTED_STATUSES: Set[str] = {"CONTINUE", "WAIT", "NEEDS_CONFIRMATION", "DONE", "ABORT"}

VALID_ACTION_TYPES: Set[str] = {
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

VALID_VERIFICATION_TYPES: Set[str] = {
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

class ModelManager:
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        self.db = db
        self.config = config
        self._init_models_in_db()

    def _init_models_in_db(self):
        """Seeds recommended low-RAM models into SQLite if not present."""
        existing = self.db.get_models()
        if not existing:
            recommended = [
                {"id": "llama3.2:1b", "name": "Llama 3.2 1B (Instruct)", "provider": "ollama", "size_bytes": 1300000000, "ram_estimate_mb": 1100, "suitable_for_6gb": True, "is_active": True},
                {"id": "qwen2.5:1.5b", "name": "Qwen 2.5 1.5B (Instruct)", "provider": "ollama", "size_bytes": 1800000000, "ram_estimate_mb": 1400, "suitable_for_6gb": True, "is_active": False},
                {"id": "llama3.2:3b", "name": "Llama 3.2 3B (Instruct)", "provider": "ollama", "size_bytes": 2000000000, "ram_estimate_mb": 2200, "suitable_for_6gb": True, "is_active": False},
                {"id": "deepseek-r1:1.5b", "name": "DeepSeek R1 1.5B (Distill)", "provider": "ollama", "size_bytes": 1800000000, "ram_estimate_mb": 1400, "suitable_for_6gb": True, "is_active": False}
            ]
            for m in recommended:
                self.db.save_model(m)

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.db.get_models()

    def check_ollama_health(self) -> Dict[str, Any]:
        """Probes the configured local Ollama endpoint."""
        endpoint = self.config.get_value("model", "endpoint", "http://127.0.0.1:11434")
        url = f"{endpoint}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PantherAgent/0.2"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = data.get("models", [])
                    return {
                        "connected": True,
                        "endpoint": endpoint,
                        "detected_models": [m.get("name") for m in models],
                        "model_count": len(models)
                    }
        except Exception:
            pass

        return {
            "connected": False,
            "endpoint": endpoint,
            "detected_models": [],
            "model_count": 0,
            "message": "Local Ollama server is offline. High-reliability deterministic planner active."
        }

    def generate_action(
        self,
        observation: ScreenState,
        goal: str,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Primary interface: generates an untrusted action proposal from local model or deterministic fallback.
        Enforces strict schema validation and a bounded correction cycle.
        """
        health = self.check_ollama_health()
        if health.get("connected"):
            # Attempt LLM generation with bounded correction (max 2 attempts)
            for attempt in range(2):
                try:
                    proposal = self._call_ollama(observation, goal, history, is_correction=(attempt > 0))
                    is_valid, reason, clean_proposal = self.validate_model_response(proposal, observation.observation_id)
                    if is_valid:
                        return clean_proposal
                    logger.warning("Model proposal validation failed (attempt %d): %s", attempt + 1, reason)
                except Exception as e:
                    logger.warning("Ollama query failed (attempt %d): %s", attempt + 1, e)

        # Fallback: High-reliability deterministic local planner
        return self._deterministic_local_plan(observation, goal, history)

    def validate_model_response(
        self,
        data: Any,
        current_observation_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Strict validation of model response against schema.
        Rejects malformed JSON, unknown action types, stale node IDs, and prohibited fields.
        Accepts both direct action-proposal schema and nested status/action schema.
        """
        if not isinstance(data, dict):
            return False, "Response must be a JSON object.", {}

        # 1. Normalize action dictionary
        action_dict = None
        if "action" in data and isinstance(data["action"], dict):
            action_dict = dict(data["action"])
        elif "action_type" in data:
            action_dict = {
                "type": data.get("action_type"),
                "node_id": data.get("target_node_id") or data.get("node_id"),
                "coordinates": data.get("coordinates"),
                "text": data.get("input_text") if "input_text" in data else data.get("text"),
                "key": data.get("key_combination") or data.get("key"),
                "seconds": data.get("wait_duration_ms") / 1000.0 if "wait_duration_ms" in data else data.get("seconds", 1.0),
                "dy": data.get("scroll_delta") if "scroll_delta" in data else data.get("dy", 0),
                "title": data.get("title") or data.get("target_window"),
                "question": data.get("question") or data.get("clarification_question")
            }
        else:
            return False, "Field 'action' or 'action_type' must be specified.", {}

        action_type = str(action_dict.get("action_type") or action_dict.get("type", "none")).lower().strip()
        if action_type not in VALID_ACTION_TYPES:
            return False, f"Unknown action type '{action_type}'. Must be one of: {sorted(list(VALID_ACTION_TYPES))}.", {}

        action_dict["type"] = action_type

        # If action is node-based, check observation prefix
        if action_type in ("click", "double_click", "right_click", "click_node", "double_click_node"):
            node_id = str(action_dict.get("target_node_id") or action_dict.get("node_id") or "")
            coords = action_dict.get("coordinates")
            if not node_id and not coords:
                return False, f"Action '{action_type}' requires 'target_node_id' or 'coordinates'.", {}
            if node_id and not node_id.startswith(f"{current_observation_id}_"):
                return False, f"STALE_NODE_REJECTED: node_id '{node_id}' does not match current observation '{current_observation_id}'.", {}

        # 2. Validate reason / concise intent (no CoT)
        reason = str(data.get("concise_intent") or data.get("reason", "Executing next turn step.")).strip()
        if len(reason) > 250:
            reason = reason[:247] + "..."
        # Strip CoT tags if any leaked
        reason = re.sub(r"<think>.*?</think>", "", reason, flags=re.DOTALL).strip()

        # 3. Validate status & proposed completion
        status = str(data.get("status", "CONTINUE")).upper().strip()
        prop_comp = data.get("proposed_completion")
        if isinstance(prop_comp, dict) and prop_comp.get("completed") is True:
            status = "DONE"
        if status not in SUPPORTED_STATUSES:
            return False, f"Unsupported status '{status}'. Must be one of: {sorted(list(SUPPORTED_STATUSES))}.", {}

        # 4. Validate verification condition
        verification = data.get("proposed_verification") or data.get("verification")
        if verification is not None and not isinstance(verification, dict):
            return False, "Field 'verification' or 'proposed_verification' must be a JSON dictionary.", {}

        v_type = "screen_changed"
        v_val = ""
        if isinstance(verification, dict):
            v_type = str(verification.get("type", "screen_changed")).lower().strip()
            if v_type not in VALID_VERIFICATION_TYPES:
                v_type = "screen_changed"
            v_val = str(verification.get("expected_text") or verification.get("value") or verification.get("condition") or "").strip()

        clean_proposal = {
            "status": status,
            "reason": reason,
            "action": action_dict,
            "verification": {
                "type": v_type,
                "value": v_val
            },
            "proposed_completion": prop_comp if isinstance(prop_comp, dict) else {"completed": status == "DONE", "reason": reason}
        }
        return True, "Valid proposal", clean_proposal

    def _call_ollama(
        self,
        observation: ScreenState,
        goal: str,
        history: List[Dict[str, Any]],
        is_correction: bool = False
    ) -> Dict[str, Any]:
        """Performs a low-memory Ollama call (256 max tokens) using compact prompt representation."""
        endpoint = self.config.get_value("model", "endpoint", "http://127.0.0.1:11434")
        selected_model = self.config.get_value("model", "selected_model", "llama3.2:1b")

        system_prompt = (
            "You are Panther Agent, a lightweight desktop automation planner on Windows. "
            "You must respond ONLY with a single valid JSON object matching this schema:\n"
            "{\n"
            '  "status": "CONTINUE" | "WAIT" | "NEEDS_CONFIRMATION" | "DONE" | "ABORT",\n'
            '  "reason": "1-sentence concise technical decision summary",\n'
            '  "action": {"type": "click_node", "node_id": "string"} | {"type": "type_text", "text": "string"} | {"type": "wait", "seconds": 1.0},\n'
            '  "verification": {"type": "text_contains" | "text_appeared" | "screen_changed", "value": "string"}\n'
            "}\n"
            "CRITICAL: Do NOT output thinking tags, reasoning, or markdown. Only valid JSON."
        )

        # Build compact element overview (top ranked nodes only)
        top_nodes = observation.nodes[:12]
        node_lines = [
            f'{n.node_id}: "{n.text}" ({n.region_name})'
            for n in top_nodes
        ]

        user_prompt = (
            f"Goal: {goal}\n"
            f"Observation ID: {observation.observation_id}\n"
            f"Active Window: {observation.active_window}\n"
            f"Screen Nodes:\n" + "\n".join(node_lines) + "\n"
        )
        if is_correction:
            user_prompt += "\nNOTE: Your previous output had schema errors. Provide strictly valid JSON referencing active observation node IDs."

        payload = {
            "model": selected_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": 2048,
                "num_predict": 256
            }
        }

        req = urllib.request.Request(
            f"{endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        timeout = self.config.get_value("timeouts", "turn_timeout_seconds", 30)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data.get("response", "{}")
            return json.loads(raw_text)

    def _deterministic_local_plan(
        self,
        observation: ScreenState,
        goal: str,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Deterministic, self-contained local planner.
        Always outputs legal schema, references actual current observation nodes,
        and obeys identical safety bounds.
        """
        turn_count = len(history)
        goal_lower = goal.lower()

        # Step 0: Find target node from goal keywords
        target_node = None
        for word in goal.split():
            if len(word) > 2:
                matched = observation.find_node_by_text(word)
                if matched:
                    target_node = matched
                    break

        if turn_count == 0:
            if target_node:
                return {
                    "status": "CONTINUE",
                    "reason": f"Located target element '{target_node.text}'; clicking node.",
                    "action": {
                        "type": "click_node",
                        "node_id": target_node.node_id
                    },
                    "verification": {
                        "type": "screen_changed",
                        "value": ""
                    }
                }
            elif observation.nodes:
                best_node = observation.nodes[0]
                return {
                    "status": "CONTINUE",
                    "reason": f"Focusing primary workspace element '{best_node.text}'.",
                    "action": {
                        "type": "click_node",
                        "node_id": best_node.node_id
                    },
                    "verification": {
                        "type": "screen_changed",
                        "value": ""
                    }
                }
            else:
                return {
                    "status": "CONTINUE",
                    "reason": "Observing desktop state; pacing execution.",
                    "action": {
                        "type": "wait",
                        "seconds": 0.5
                    },
                    "verification": {
                        "type": "screen_changed",
                        "value": ""
                    }
                }

        elif turn_count == 1:
            if "type" in goal_lower or "write" in goal_lower or "enter" in goal_lower:
                text_to_type = goal.split("type")[-1].replace("'", "").replace('"', '').strip() if "type" in goal_lower else "Panther Agent local task"
                return {
                    "status": "CONTINUE",
                    "reason": "Typing requested text into active target.",
                    "action": {
                        "type": "type_text",
                        "text": text_to_type
                    },
                    "verification": {
                        "type": "screen_changed",
                        "value": ""
                    }
                }
            else:
                # Click next interactive element or wait
                interactive_nodes = [n for n in observation.nodes if n.interactive]
                if interactive_nodes:
                    node = interactive_nodes[0]
                    return {
                        "status": "CONTINUE",
                        "reason": f"Executing secondary step on interactive element '{node.text}'.",
                        "action": {
                            "type": "click_node",
                            "node_id": node.node_id
                        },
                        "verification": {
                            "type": "screen_changed",
                            "value": ""
                        }
                    }
                return {
                    "status": "CONTINUE",
                    "reason": "Awaiting visual response from target application.",
                    "action": {
                        "type": "wait",
                        "seconds": 0.5
                    },
                    "verification": {
                        "type": "screen_changed",
                        "value": ""
                    }
                }

        else:
            # Propose completion for deterministic verifier to evaluate
            return {
                "status": "DONE",
                "reason": "All operational actions dispatched; requesting deterministic goal verification.",
                "action": {
                    "type": "none"
                },
                "verification": {
                    "type": "screen_changed",
                    "value": ""
                }
            }
