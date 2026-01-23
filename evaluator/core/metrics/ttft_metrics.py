# evaluator/metrics/ttft_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class TTFTMetric(BaseMetric):
    """
    Tracks Time to First Token (TTFT) for each LLM call.
    TTFT is the latency between LLM_QUERY_START and LLM_FIRST_TOKEN_RECEIVED.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.ttft_measurements: List[float] = []  # Store all TTFT values in milliseconds
        self.pending_start_time: Optional[float] = None  # Track unpaired LLM_QUERY_START

    def get_name(self) -> str:
        return "ttft_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.LLM_QUERY_START:
            # Record the start time for this LLM query
            self.pending_start_time = timestamp
            self.logger.debug(f"LLM query started at {timestamp}")

        elif event_type == AgentEvent.LLM_FIRST_TOKEN_RECEIVED:
            # Calculate TTFT if we have a pending start time
            if self.pending_start_time is not None and timestamp is not None:
                ttft_seconds = timestamp - self.pending_start_time
                ttft_ms = ttft_seconds * 1000  # Convert to milliseconds
                self.ttft_measurements.append(ttft_ms)
                self.logger.debug(f"TTFT measured: {ttft_ms:.2f} ms")
                self.pending_start_time = None  # Clear for next measurement
            else:
                self.logger.warning(f"Received LLM_FIRST_TOKEN_RECEIVED without matching LLM_QUERY_START")

    def get_value(self) -> Dict[str, Any]:
        if not self.ttft_measurements:
            return {
                "average_ttft_ms": None,
                "min_ttft_ms": None,
                "max_ttft_ms": None,
                "total_llm_calls": 0,
                "all_ttft_ms": []
            }

        return {
            "average_ttft_ms": round(sum(self.ttft_measurements) / len(self.ttft_measurements), 2),
            "min_ttft_ms": round(min(self.ttft_measurements), 2),
            "max_ttft_ms": round(max(self.ttft_measurements), 2),
            "total_llm_calls": len(self.ttft_measurements),
            "all_ttft_ms": [round(t, 2) for t in self.ttft_measurements]
        }

    def reset(self) -> None:
        super().reset()
        self.ttft_measurements = []
        self.pending_start_time = None
