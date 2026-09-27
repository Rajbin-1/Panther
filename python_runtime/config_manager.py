"""
Panther Agent - Configuration Manager
Centralized, persistent configuration backed by SQLite.
Optimized for low-resource Windows execution (6 GB RAM target).
"""

from typing import Any, Dict, Optional
import logging
from database import DatabaseManager

logger = logging.getLogger("panther.config")

# Default profiles tailored for low-resource 6GB Windows hardware
DEFAULT_CONFIG: Dict[str, Any] = {
    # 1. Model Configuration
    "model": {
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "selected_model": "llama3.2:1b",
        "fallback_model": "qwen2.5:1.5b",
        "temperature": 0.1,
        "max_context_tokens": 2048,  # Constrained for 6GB RAM
        "max_predict_tokens": 256,
        "request_timeout_seconds": 30,
        "keep_alive": "5m",  # Unload from RAM when inactive
    },

    # 2. OCR Configuration
    "ocr": {
        "primary_engine": "windows_media_ocr",  # Windows Native Media OCR
        "fallback_engine": "mock_tesseract",
        "language": "en-US",
        "downscale_factor": 1.0,  # 1.0 = native, 0.75 = memory saver
        "grayscale_preprocessing": True,
        "cache_ocr_results": True,
        "confidence_threshold": 0.65,
    },

    # 3. Action Limits & Throttling
    "action_limits": {
        "max_actions_per_turn": 3,
        "min_delay_between_actions_ms": 350,
        "max_mouse_speed": "normal",
        "type_interval_ms": 25,
        "require_element_visibility": True,
    },

    # 4. Timeout Limits
    "timeouts": {
        "turn_timeout_seconds": 45,
        "action_execution_timeout_seconds": 15,
        "verification_timeout_seconds": 10,
        "total_task_timeout_seconds": 300,
    },

    # 5. Retry Limits
    "retries": {
        "max_action_retries": 2,
        "max_verification_retries": 2,
        "max_turn_recovery_attempts": 3,
    },

    # 6. Resource Limits (Strictly tuned for 6 GB RAM & low-end dual-core CPU)
    "resource_limits": {
        "min_available_ram_mb": 1024,      # Warn / pause if free RAM < 1 GB
        "critical_available_ram_mb": 512,  # Emergency stop if free RAM < 512 MB
        "max_agent_ram_mb": 450,           # Python runtime footprint limit
        "max_cpu_percent_sustained": 85.0, # Throttle if CPU > 85% for 3 cycles
        "screen_capture_interval_ms": 600, # Rate limit screen polling to conserve CPU
        "enable_governor_throttling": True,
    },

    # 7. Safety Configuration (Strict Untrusted Action Boundary)
    "safety": {
        "allow_shell_commands": False,       # NEVER allow arbitrary shell
        "allow_executable_launch": False,   # NEVER allow arbitrary binaries
        "allow_filesystem_mod": False,      # NEVER allow arbitrary file deletes/overwrites
        "require_confirmation_for_destructive": True,
        "allowed_key_combinations": [
            "ctrl+c", "ctrl+v", "ctrl+a", "ctrl+s", "ctrl+z", "enter", "tab", "escape", "backspace", "space"
        ],
        "forbidden_key_combinations": [
            "alt+f4", "ctrl+alt+del", "win+l", "format", "shutdown"
        ],
        "allowed_url_schemes": ["https", "http"],
        "screen_bounds_enforced": True,
    },

    # 8. UI Configuration
    "ui": {
        "theme": "light",
        "density": "comfortable",
        "sound_effects": False,
        "show_resource_governor_bar": True,
        "notifications_enabled": True,
    },

    # 9. Voice Configuration (Future extensibility)
    "voice": {
        "enabled": False,
        "engine": "none",
        "input_device_id": "default",
        "hotword_enabled": False,
    },

    # 10. Installation & Setup State
    "installation": {
        "initialized": False,
        "version": "0.1.0-alpha",
        "platform_target": "windows",
        "setup_completed": False,
    }
}

class ConfigManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Populates any missing default configuration sections into SQLite."""
        for section, defaults in DEFAULT_CONFIG.items():
            existing = self.db.get_config(section)
            if existing is None:
                self.db.set_config(section, defaults)
            elif isinstance(existing, dict) and isinstance(defaults, dict):
                # Merge missing keys into existing config
                merged = {**defaults, **existing}
                if merged != existing:
                    self.db.set_config(section, merged)

    def get_section(self, section: str) -> Dict[str, Any]:
        val = self.db.get_config(section)
        if isinstance(val, dict):
            return val
        return DEFAULT_CONFIG.get(section, {})

    def get_value(self, section: str, key: str, default: Any = None) -> Any:
        sec = self.get_section(section)
        return sec.get(key, default)

    def update_section(self, section: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_section(section)
        current.update(updates)
        self.db.set_config(section, current)
        logger.info("Updated config section '%s': %s", section, list(updates.keys()))
        return current

    def get_full_config(self) -> Dict[str, Any]:
        result = {}
        for section in DEFAULT_CONFIG.keys():
            result[section] = self.get_section(section)
        return result

    def reset_to_defaults(self) -> Dict[str, Any]:
        for section, defaults in DEFAULT_CONFIG.items():
            self.db.set_config(section, defaults)
        return self.get_full_config()
