# evaluator/metrics/tool_confidence_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class ToolConfidenceMetric(BaseMetric):
    """
    Tracks tool call confidence scores derived from logprobs.
    Listens to TOOL_CALL_START events and collects the 'confidence' field
    when present (populated by the OpenAI adapter from logprobs data).
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.confidences: List[float] = []

    def get_name(self) -> str:
        return "tool_confidence_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        if event_type == AgentEvent.TOOL_CALL_START:
            confidence = data.get("confidence")
            if confidence is not None:
                try:
                    conf_val = float(confidence)
                    self.confidences.append(conf_val)
                    self.logger.debug(
                        "Tool confidence: %.4f for %s",
                        conf_val,
                        data.get("tool_name", "unknown"),
                    )
                except (TypeError, ValueError):
                    pass

    def get_value(self) -> Dict[str, Any]:
        if not self.confidences:
            return {
                "avg_tool_confidence": None,
                "min_tool_confidence": None,
                "max_tool_confidence": None,
                "tool_calls_with_confidence": 0,
            }
        return {
            "avg_tool_confidence": round(sum(self.confidences) / len(self.confidences), 4),
            "min_tool_confidence": round(min(self.confidences), 4),
            "max_tool_confidence": round(max(self.confidences), 4),
            "tool_calls_with_confidence": len(self.confidences),
        }

    def reset(self) -> None:
        super().reset()
        self.confidences = []
