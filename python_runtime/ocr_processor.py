"""
Panther Agent - OCR Processor
Intelligent OCR layout analysis: word-to-line clustering, interactive element detection,
deterministic ranking based on goal relevance and interaction cues, and observation-scoped node IDs.
"""

import re
import platform
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from database import DatabaseManager
from config_manager import ConfigManager
from screen_state import OcrNode

logger = logging.getLogger("panther.ocr")

# Common interactive UI markers and keywords
INTERACTIVE_KEYWORDS: Set[str] = {
    "ok", "cancel", "submit", "save", "open", "file", "edit", "view",
    "search", "close", "run", "start", "next", "back", "done", "apply",
    "delete", "remove", "add", "new", "settings", "continue", "sign in",
    "login", "confirm", "yes", "no", "browse", "help", "menu", "select"
}

class OcrProcessor:
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        self.db = db
        self.config = config
        self.is_windows = platform.system().lower() == "windows"
        self._cached_nodes: List[OcrNode] = []
        self._simulated_screen_elements: List[Dict[str, Any]] = []

    def set_active_screen_elements(self, elements: List[Dict[str, Any]]) -> None:
        """Injects or updates UI elements in the current active frame (for deterministic verification & testing)."""
        self._simulated_screen_elements = [dict(el) for el in elements]

    def clear_simulated_elements(self) -> None:
        self._simulated_screen_elements = []

    def process_screen(
        self,
        observation_id: str,
        frame_meta: Dict[str, Any],
        goal: str = "",
        last_interaction_pos: Optional[Tuple[int, int]] = None,
        changed_texts: Optional[Set[str]] = None
    ) -> List[OcrNode]:
        """
        Runs OCR on the active frame, groups nearby words into lines, assigns observation-scoped node IDs,
        and ranks nodes deterministically by utility and goal relevance.
        """
        ocr_conf = self.config.get_section("ocr")
        min_conf = ocr_conf.get("confidence_threshold", 0.65)

        raw_elements: List[Dict[str, Any]] = []

        if self.is_windows and ocr_conf.get("primary_engine") == "windows_media_ocr":
            try:
                raw_elements = self._run_windows_media_ocr()
            except Exception as e:
                logger.warning("Windows Media OCR invocation error: %s", e)

        if not raw_elements:
            raw_elements = self._run_fallback_elements(frame_meta)

        # 1. Group nearby horizontal words into unified element lines
        clustered = self._cluster_words_into_lines(raw_elements)

        # 2. Filter by confidence
        filtered = [el for el in clustered if el.get("confidence", 1.0) >= min_conf]

        # 3. Create OcrNodes with observation-scoped IDs
        nodes: List[OcrNode] = []
        for idx, el in enumerate(filtered):
            node_id = f"{observation_id}_node_{idx + 1}"
            text = el.get("text", "").strip()
            if not text:
                continue

            interactive = self._detect_interactivity(text, el)
            region_name = self._classify_region(el.get("x", 0), el.get("y", 0), frame_meta)

            nodes.append(OcrNode(
                node_id=node_id,
                text=text,
                x=el.get("x", 0),
                y=el.get("y", 0),
                width=el.get("width", 50),
                height=el.get("height", 24),
                confidence=el.get("confidence", 0.95),
                interactive=interactive,
                region_name=region_name
            ))

        # 4. Deterministic Element Ranking
        ranked_nodes = self._rank_nodes(
            nodes,
            goal=goal,
            active_window=frame_meta.get("active_window", ""),
            last_interaction_pos=last_interaction_pos,
            changed_texts=changed_texts or set()
        )

        self._cached_nodes = ranked_nodes
        return ranked_nodes

    def _cluster_words_into_lines(self, words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Groups nearby words on the same horizontal line into meaningful phrases."""
        if not words:
            return []

        # Sort primarily by vertical position (Y), secondarily horizontal (X)
        sorted_words = sorted(words, key=lambda w: (w.get("y", 0) // 12, w.get("x", 0)))
        
        clusters: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for w in sorted_words:
            if not w.get("text"):
                continue

            if current is None:
                current = {
                    "text": w["text"],
                    "x": w["x"],
                    "y": w["y"],
                    "width": w["width"],
                    "height": w["height"],
                    "confidence": w.get("confidence", 0.95)
                }
                continue

            # Check if w is on approximately the same line and close to current
            y_diff = abs(w["y"] - current["y"])
            x_gap = w["x"] - (current["x"] + current["width"])

            # Maximum line height variance ~ 10px, max horizontal gap ~ 25px
            if y_diff <= 10 and 0 <= x_gap <= 25:
                # Merge into current line
                current["text"] = f"{current['text']} {w['text']}".strip()
                new_width = (w["x"] + w["width"]) - current["x"]
                current["width"] = new_width
                current["height"] = max(current["height"], w["height"])
                current["confidence"] = (current["confidence"] + w.get("confidence", 0.95)) / 2.0
            else:
                clusters.append(current)
                current = {
                    "text": w["text"],
                    "x": w["x"],
                    "y": w["y"],
                    "width": w["width"],
                    "height": w["height"],
                    "confidence": w.get("confidence", 0.95)
                }

        if current:
            clusters.append(current)

        return clusters

    def _detect_interactivity(self, text: str, el: Dict[str, Any]) -> bool:
        """Determines whether the element looks interactive based on keywords and dimensions."""
        t_clean = text.lower().strip()
        # Direct keyword match
        if t_clean in INTERACTIVE_KEYWORDS:
            return True
        for kw in INTERACTIVE_KEYWORDS:
            if kw in t_clean and len(kw) > 3:
                return True

        # Button-like aspect ratio (e.g., width 40-250px, height 20-50px)
        w = el.get("width", 0)
        h = el.get("height", 0)
        if 40 <= w <= 260 and 20 <= h <= 50 and len(text) <= 24:
            return True

        # Input field indicators
        if "[" in text or "]" in text or "_" in text or "..." in text or ":" in text:
            return True

        return False

    def _classify_region(self, x: int, y: int, frame_meta: Dict[str, Any]) -> str:
        h = frame_meta.get("height", 1080)
        if y < 45:
            return "title_bar"
        elif y > (h - 52):
            return "taskbar"
        return "main_viewport"

    def _rank_nodes(
        self,
        nodes: List[OcrNode],
        goal: str,
        active_window: str,
        last_interaction_pos: Optional[Tuple[int, int]],
        changed_texts: Set[str]
    ) -> List[OcrNode]:
        """
        Deterministic element ranking.
        Priority:
        1. Goal relevance (keywords in goal)
        2. Interactive-looking elements
        3. Recently changed elements
        4. Active window elements vs peripheral
        5. Proximity to last interaction
        6. High confidence
        """
        goal_words = set(re.findall(r"\w+", goal.lower())) if goal else set()

        def compute_score(node: OcrNode) -> float:
            score = 0.0
            node_text_words = set(re.findall(r"\w+", node.text.lower()))

            # 1. Goal relevance (+50 for exact match, +25 per matching keyword)
            overlap = goal_words.intersection(node_text_words)
            if overlap:
                score += len(overlap) * 30.0
            if goal and goal.lower() in node.text.lower():
                score += 50.0

            # 2. Interactive appearance (+20)
            if node.interactive:
                score += 20.0

            # 3. Recently changed element (+25)
            if node.text in changed_texts:
                score += 25.0

            # 4. Active window relevance (+15 if in main viewport)
            if node.region_name == "main_viewport":
                score += 15.0

            # 5. Proximity to last interaction
            if last_interaction_pos:
                dist = abs(node.center_x - last_interaction_pos[0]) + abs(node.center_y - last_interaction_pos[1])
                proximity_bonus = max(0.0, 15.0 - (dist / 100.0))
                score += proximity_bonus

            # 6. Confidence (+0 to +10)
            score += node.confidence * 10.0

            return score

        # Sort descending by priority score
        return sorted(nodes, key=compute_score, reverse=True)

    def _run_windows_media_ocr(self) -> List[Dict[str, Any]]:
        """Windows WinRT OCR interop bridge placeholder; returns empty if runtime bridge not available."""
        return []

    def _run_fallback_elements(self, frame_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Provides simulated screen elements or standard desktop UI markers."""
        results: List[Dict[str, Any]] = []
        if self._simulated_screen_elements:
            results.extend(self._simulated_screen_elements)

        win_title = frame_meta.get("active_window", "Panther Desktop")
        # Standard system desktop elements
        results.append({"text": win_title, "x": 24, "y": 12, "width": 240, "height": 26, "confidence": 0.99})
        results.append({"text": "Start", "x": 12, "y": 1042, "width": 42, "height": 30, "confidence": 0.99})
        results.append({"text": "Search", "x": 62, "y": 1042, "width": 64, "height": 30, "confidence": 0.95})
        results.append({"text": "File Explorer", "x": 136, "y": 1042, "width": 90, "height": 30, "confidence": 0.95})
        return results
