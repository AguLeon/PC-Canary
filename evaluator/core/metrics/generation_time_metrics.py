# evaluator/metrics/generation_time_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class GenerationTimeMetric(BaseMetric):
    """
    Tracks total LLM generation time for each LLM call.
    Generation time is measured as the total time from LLM_QUERY_START to LLM_QUERY_END,
    which includes both prompt processing and token generation.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.generation_times: List[float] = []  # Store all generation times in milliseconds
        self.pending_start_time: Optional[float] = None  # Track unpaired LLM_QUERY_START

    def get_name(self) -> str:
        return "generation_time_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.LLM_QUERY_START:
            # Record the start time for this LLM query
            self.pending_start_time = timestamp
            self.logger.debug(f"LLM generation started at {timestamp}")

        elif event_type == AgentEvent.LLM_QUERY_END:
            # Calculate generation time if we have a pending start time
            if self.pending_start_time is not None and timestamp is not None:
                status = data.get('status')
                if status == 'success':
                    generation_time_seconds = timestamp - self.pending_start_time
                    generation_time_ms = generation_time_seconds * 1000  # Convert to milliseconds
                    self.generation_times.append(generation_time_ms)
                    self.logger.debug(f"Generation time measured: {generation_time_ms:.2f} ms")
                else:
                    # LLM query failed, don't record timing
                    self.logger.debug(f"LLM query failed with status '{status}', skipping generation time measurement")
                self.pending_start_time = None  # Clear for next measurement
            else:
                self.logger.warning(f"Received LLM_QUERY_END without matching LLM_QUERY_START")

    def get_value(self) -> Dict[str, Any]:
        if not self.generation_times:
            return {
                "average_generation_time_ms": None,
                "min_generation_time_ms": None,
                "max_generation_time_ms": None,
                "total_llm_calls": 0,
                "all_generation_times_ms": []
            }

        return {
            "average_generation_time_ms": round(sum(self.generation_times) / len(self.generation_times), 2),
            "min_generation_time_ms": round(min(self.generation_times), 2),
            "max_generation_time_ms": round(max(self.generation_times), 2),
            "total_llm_calls": len(self.generation_times),
            "all_generation_times_ms": [round(t, 2) for t in self.generation_times]
        }

    def reset(self) -> None:
        super().reset()
        self.generation_times = []
        self.pending_start_time = None
