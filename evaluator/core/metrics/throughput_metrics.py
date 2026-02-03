# evaluator/metrics/throughput_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class ThroughputMetric(BaseMetric):
    """
    Tracks inference throughput (tokens per second) per LLM call and aggregated.
    Combines completion_tokens from LLM_QUERY_END with the elapsed time
    between LLM_QUERY_START and LLM_QUERY_END.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.per_call_throughput: List[float] = []
        self.total_completion_tokens: int = 0
        self.total_generation_time_sec: float = 0.0
        self.pending_start_time: Optional[float] = None

    def get_name(self) -> str:
        return "throughput_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get("timestamp")

        if event_type == AgentEvent.LLM_QUERY_START:
            self.pending_start_time = timestamp

        elif event_type == AgentEvent.LLM_QUERY_END:
            if (
                self.pending_start_time is not None
                and timestamp is not None
                and data.get("status") == "success"
            ):
                gen_time_sec = timestamp - self.pending_start_time
                completion_tokens = data.get("completion_tokens") or 0

                if gen_time_sec > 0 and completion_tokens > 0:
                    tps = completion_tokens / gen_time_sec
                    self.per_call_throughput.append(tps)
                    self.total_completion_tokens += completion_tokens
                    self.total_generation_time_sec += gen_time_sec
                    self.logger.debug(
                        f"Throughput: {tps:.2f} tok/s "
                        f"({completion_tokens} tokens in {gen_time_sec:.2f}s)"
                    )

            self.pending_start_time = None

    def get_value(self) -> Dict[str, Any]:
        if not self.per_call_throughput:
            return {
                "avg_tokens_per_second": None,
                "min_tokens_per_second": None,
                "max_tokens_per_second": None,
                "overall_tokens_per_second": None,
                "total_completion_tokens": 0,
                "total_generation_time_sec": 0.0,
                "call_count": 0,
            }

        overall_tps = (
            self.total_completion_tokens / self.total_generation_time_sec
            if self.total_generation_time_sec > 0
            else 0.0
        )

        return {
            "avg_tokens_per_second": round(
                sum(self.per_call_throughput) / len(self.per_call_throughput), 2
            ),
            "min_tokens_per_second": round(min(self.per_call_throughput), 2),
            "max_tokens_per_second": round(max(self.per_call_throughput), 2),
            "overall_tokens_per_second": round(overall_tps, 2),
            "total_completion_tokens": self.total_completion_tokens,
            "total_generation_time_sec": round(self.total_generation_time_sec, 2),
            "call_count": len(self.per_call_throughput),
        }

    def reset(self) -> None:
        super().reset()
        self.per_call_throughput = []
        self.total_completion_tokens = 0
        self.total_generation_time_sec = 0.0
        self.pending_start_time = None
