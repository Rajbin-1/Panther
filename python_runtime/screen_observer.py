"""
Panther Agent - Screen Observer
Captures real Windows desktop observation metadata, manages observation IDs,
evaluates perceptual / differential screen hashes, and constructs complete ScreenStates.
"""

import time
import hashlib
import platform
import logging
from typing import Dict, Any, Optional, Tuple, List, Set
from database import DatabaseManager
from config_manager import ConfigManager
from screen_state import ScreenState, ScreenStateDiff, OcrNode, VisualRegion
from ocr_processor import OcrProcessor

logger = logging.getLogger("panther.screen_observer")

class ScreenObserver:
    def __init__(self, db: DatabaseManager, config: ConfigManager, ocr_processor: OcrProcessor):
        self.db = db
        self.config = config
        self.ocr = ocr_processor
        self.is_windows = platform.system().lower() == "windows"

        self._observation_seq: int = 0
        self._current_state: Optional[ScreenState] = None
        self._previous_state: Optional[ScreenState] = None
        self._last_state_diff: Optional[Dict[str, Any]] = None
        self._last_fingerprint: Optional[str] = None
        self._last_capture_time: float = 0
        self._action_mutation_counter: int = 0

    def notify_action_executed(self, action_type: str):
        """Called by action executor to notify that an action was executed and may have mutated the screen."""
        self._action_mutation_counter += 1

    def invalidate_cache(self):
        """Forces the next observation to capture freshly."""
        self._last_fingerprint = None

    def get_current_observation(self) -> Optional[ScreenState]:
        return self._current_state

    def get_previous_observation(self) -> Optional[ScreenState]:
        return self._previous_state

    def get_last_diff(self) -> Optional[Dict[str, Any]]:
        return self._last_state_diff

    def observe(
        self,
        force: bool = False,
        goal: str = "",
        last_interaction_pos: Optional[Tuple[int, int]] = None
    ) -> ScreenState:
        """
        Observes the screen. If the screen has not meaningfully changed and not forced,
        reuses the current valid ScreenState to conserve RAM and CPU on low-resource hardware.
        When changed, generates a new observation ID and regenerates observation-scoped node IDs.
        """
        now = time.time()
        res_limits = self.config.get_section("resource_limits")
        min_interval = res_limits.get("screen_capture_interval_ms", 600) / 1000.0

        # Retrieve window info and compute fingerprint
        win_title, bounds, dpi = self._get_active_window_info()
        w, h = bounds[2], bounds[3]
        fingerprint = self._compute_fingerprint(win_title, bounds, self._action_mutation_counter)

        has_changed = (fingerprint != self._last_fingerprint)

        # Cache reuse condition:
        # If not forced, screen has not changed, and we have a valid current state, reuse it!
        if not force and not has_changed and self._current_state is not None:
            # Reusing existing valid state (saves full OCR cycle)
            return self._current_state

        # Otherwise, screen has changed or observation was forced
        self._observation_seq += 1
        observation_id = f"obs_{self._observation_seq}"

        frame_meta = {
            "timestamp": now,
            "width": w,
            "height": h,
            "active_window": win_title,
            "window_bounds": {"x": bounds[0], "y": bounds[1], "width": w, "height": h},
            "dpi_scaling": dpi,
            "screen_fingerprint": fingerprint
        }

        # Collect changed texts from previous diff if available
        changed_texts: Set[str] = set()
        if self._last_state_diff:
            changed_texts.update(self._last_state_diff.get("text_appeared", []))

        # Perform intelligent OCR line grouping & ranking
        nodes = self.ocr.process_screen(
            observation_id=observation_id,
            frame_meta=frame_meta,
            goal=goal,
            last_interaction_pos=last_interaction_pos,
            changed_texts=changed_texts
        )

        new_state = ScreenState(
            observation_id=observation_id,
            timestamp=now,
            width=w,
            height=h,
            active_display="DISPLAY_PRIMARY",
            dpi_scaling=dpi,
            active_window=win_title,
            active_window_bounds=frame_meta["window_bounds"],
            nodes=nodes,
            screen_fingerprint=fingerprint
        )

        # Compute deterministic diff against previous state
        diff = ScreenStateDiff.compute(self._current_state, new_state)

        self._previous_state = self._current_state
        self._current_state = new_state
        self._last_state_diff = diff
        self._last_fingerprint = fingerprint
        self._last_capture_time = now

        return new_state

    def _compute_fingerprint(self, title: str, bounds: Tuple[int, int, int, int], action_counter: int) -> str:
        """Lightweight differential hash based on window state, bounds, and action sequence."""
        h = hashlib.sha256()
        h.update(f"{title}:{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}:m_{action_counter}".encode("utf-8"))
        return h.hexdigest()[:16]

    def _get_active_window_info(self) -> Tuple[str, Tuple[int, int, int, int], float]:
        """Queries the active foreground window title, bounding rect, and DPI scaling."""
        if self.is_windows:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value or "Desktop / Active Window"

                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    rect = RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = max(0, rect.right - rect.left)
                    h = max(0, rect.bottom - rect.top)

                    # Query DPI
                    dpi_scale = 1.0
                    try:
                        hdc = user32.GetDC(hwnd)
                        gdi32 = ctypes.windll.gdi32
                        logpixelsy = gdi32.GetDeviceCaps(hdc, 90)
                        user32.ReleaseDC(hwnd, hdc)
                        dpi_scale = round(logpixelsy / 96.0, 2)
                    except Exception:
                        pass

                    return title, (rect.left, rect.top, w or 1920, h or 1080), dpi_scale
            except Exception as e:
                logger.debug("Windows active window query note: %s", e)

        # Baseline viewport fallback
        return "Panther Desktop Workspace", (0, 0, 1920, 1080), 1.0
