# evaluator/metrics/loop_detection_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class LoopDetectionMetric(BaseMetric):
    """
    Tracks loop detection events - when the agent repeats tool calls in patterns.

    Detects two types of loops:
    1. Consecutive identical calls (A-A-A)
    2. Alternating patterns (A-B-A-B-A-B)

    Note: Loop detection does NOT intervene with execution - it only tracks for metrics.

    Tracks:
    - Whether any loops were detected (boolean flag)
    - Total count of loop detections
    - Types of loops detected
    - Detailed list of each loop with description and timestamp
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.current_turn: int = 0  # Track which turn we're on
        self.loop_detections: List[Dict[str, Any]] = []  # Each loop detection with details
        self.loop_types: Dict[str, int] = {}  # Count of each type of loop

    def get_name(self) -> str:
        return "loop_detection_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.LLM_QUERY_START:
            # Each LLM query marks the start of a new turn
            self.current_turn += 1
            self.logger.debug(f"Starting turn {self.current_turn}")

        elif event_type == AgentEvent.TOOL_CALL_END:
            # Check if this is a loop detection event
            tool_name = data.get('tool_name')

            if tool_name == 'loop_detection':
                loop_description = data.get('result', 'Unknown loop pattern')

                self.logger.info(
                    f"LOOP DETECTED in turn {self.current_turn}: {loop_description}"
                )

                # Extract loop type from description
                loop_type = "unknown"
                if "consecutive identical" in loop_description:
                    loop_type = "consecutive_identical"
                elif "alternating pattern" in loop_description:
                    loop_type = "alternating_pattern"

                # Record the loop detection
                self.loop_detections.append({
                    "turn": self.current_turn,
                    "loop_type": loop_type,
                    "description": loop_description,
                    "timestamp": timestamp,
                })

                # Count loop types
                self.loop_types[loop_type] = self.loop_types.get(loop_type, 0) + 1

    def get_value(self) -> Dict[str, Any]:
        """
        Return loop detection metrics.

        Returns:
            Dict containing:
            - loop_detected: Boolean flag (True if any loops were detected)
            - total_loop_detections: Total count of loop detections
            - loop_types: Dictionary mapping loop type to count
            - loop_details: List of all loop detections with turn, type, description, and timestamp
        """
        loop_detected = len(self.loop_detections) > 0

        return {
            "loop_detected": loop_detected,
            "total_loop_detections": len(self.loop_detections),
            "loop_types": self.loop_types,
            "total_turns": self.current_turn,
            "loop_details": self.loop_detections
        }

    def reset(self) -> None:
        """Reset all tracking state."""
        super().reset()
        self.current_turn = 0
        self.loop_detections = []
        self.loop_types = {}
