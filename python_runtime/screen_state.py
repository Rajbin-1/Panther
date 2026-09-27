"""
Panther Agent - Screen State & Diff Engine
Defines rich ScreenState, OcrNode, VisualRegion, and deterministic state-diff computation.
Enforces observation-scoped node IDs (e.g., 'obs_42_node_7').
"""

import time
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple

class OcrNode:
    def __init__(
        self,
        node_id: str,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
        confidence: float = 0.95,
        interactive: bool = False,
        region_name: str = "main_content"
    ):
        self.node_id = node_id
        self.text = text.strip()
        self.x = int(x)
        self.y = int(y)
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.confidence = float(confidence)
        self.interactive = interactive
        self.region_name = region_name

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "confidence": round(self.confidence, 2),
            "interactive": self.interactive,
            "region": self.region_name
        }

    def contains_point(self, px: int, py: int) -> bool:
        return self.x <= px <= (self.x + self.width) and self.y <= py <= (self.y + self.height)

class VisualRegion:
    def __init__(self, name: str, x: int, y: int, width: int, height: int):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x <= (self.x + self.width) and self.y <= y <= (self.y + self.height)

class ScreenState:
    def __init__(
        self,
        observation_id: str,
        timestamp: float,
        width: int,
        height: int,
        active_display: str = "DISPLAY_1",
        dpi_scaling: float = 1.0,
        active_window: str = "Desktop",
        active_window_bounds: Optional[Dict[str, int]] = None,
        nodes: Optional[List[OcrNode]] = None,
        screen_fingerprint: str = "",
        regions: Optional[List[VisualRegion]] = None
    ):
        self.observation_id = observation_id
        self.timestamp = timestamp
        self.width = width
        self.height = height
        self.active_display = active_display
        self.dpi_scaling = dpi_scaling
        self.active_window = active_window
        self.active_window_bounds = active_window_bounds or {"x": 0, "y": 0, "width": width, "height": height}
        self.nodes = nodes or []
        self.screen_fingerprint = screen_fingerprint
        self.regions = regions or self._create_default_regions(width, height)
        self._node_map: Dict[str, OcrNode] = {n.node_id: n for n in self.nodes}

    def _create_default_regions(self, width: int, height: int) -> List[VisualRegion]:
        return [
            VisualRegion("title_bar", 0, 0, width, 40),
            VisualRegion("taskbar", 0, max(0, height - 48), width, 48),
            VisualRegion("main_viewport", 0, 40, width, max(1, height - 88))
        ]

    def get_node(self, node_id: str) -> Optional[OcrNode]:
        return self._node_map.get(node_id)

    def find_node_by_text(self, text_query: str, fuzzy: bool = True) -> Optional[OcrNode]:
        q = text_query.strip().lower()
        if not q:
            return None
        # Exact match first
        for node in self.nodes:
            if node.text.lower() == q:
                return node
        # Substring / fuzzy match
        if fuzzy:
            for node in self.nodes:
                if q in node.text.lower() or node.text.lower() in q:
                    return node
        return None

    def find_nodes_by_text(self, text_query: str) -> List[OcrNode]:
        q = text_query.strip().lower()
        return [n for n in self.nodes if q in n.text.lower()]

    def to_dict(self, include_nodes: bool = True) -> Dict[str, Any]:
        data = {
            "observation_id": self.observation_id,
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
            "active_display": self.active_display,
            "dpi_scaling": self.dpi_scaling,
            "active_window": self.active_window,
            "active_window_bounds": self.active_window_bounds,
            "screen_fingerprint": self.screen_fingerprint,
            "regions": [r.to_dict() for r in self.regions],
            "total_nodes": len(self.nodes)
        }
        if include_nodes:
            data["ocr_elements"] = [n.to_dict() for n in self.nodes]
        return data

class ScreenStateDiff:
    """Computes a deterministic, evidence-based diff between two ScreenStates."""

    @staticmethod
    def compute(prev: Optional[ScreenState], curr: ScreenState) -> Dict[str, Any]:
        if prev is None:
            return {
                "changed": True,
                "fingerprint_changed": True,
                "text_appeared": [n.text for n in curr.nodes[:10]],
                "text_disappeared": [],
                "nodes_added": [n.node_id for n in curr.nodes],
                "nodes_removed": [],
                "nodes_moved": [],
                "regions_changed": ["initial_capture"],
                "window_changed": False,
                "active_window_prev": None,
                "active_window_curr": curr.active_window
            }

        fp_changed = prev.screen_fingerprint != curr.screen_fingerprint
        win_changed = prev.active_window != curr.active_window

        prev_texts: Set[str] = {n.text for n in prev.nodes if len(n.text) > 1}
        curr_texts: Set[str] = {n.text for n in curr.nodes if len(n.text) > 1}

        text_appeared = sorted(list(curr_texts - prev_texts))
        text_disappeared = sorted(list(prev_texts - curr_texts))

        # Compare node positions for persistent texts
        nodes_moved = []
        for c_node in curr.nodes:
            p_node = prev.find_node_by_text(c_node.text, fuzzy=False)
            if p_node:
                dist = abs(c_node.x - p_node.x) + abs(c_node.y - p_node.y)
                if dist > 15:
                    nodes_moved.append({
                        "text": c_node.text,
                        "from": (p_node.x, p_node.y),
                        "to": (c_node.x, c_node.y)
                    })

        # Regions that changed
        regions_changed = []
        if win_changed:
            regions_changed.append("title_bar")
        if text_appeared or text_disappeared or nodes_moved:
            regions_changed.append("main_viewport")

        is_changed = (
            fp_changed
            or win_changed
            or len(text_appeared) > 0
            or len(text_disappeared) > 0
            or len(nodes_moved) > 0
        )

        return {
            "changed": is_changed,
            "fingerprint_changed": fp_changed,
            "text_appeared": text_appeared,
            "text_disappeared": text_disappeared,
            "nodes_added": [n.node_id for n in curr.nodes if n.text not in prev_texts],
            "nodes_removed": [n.node_id for n in prev.nodes if n.text not in curr_texts],
            "nodes_moved": nodes_moved,
            "regions_changed": regions_changed,
            "window_changed": win_changed,
            "active_window_prev": prev.active_window,
            "active_window_curr": curr.active_window
        }
