# evaluator/metrics/overhead_metrics.py
from typing import Dict, Any, Optional
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class ProcessingOverheadMetric(BaseMetric):
    """
    Tracks processing overhead - time spent by the framework/system excluding LLM and tool execution.

    Processing Overhead = Total Task Time - LLM Time - Tool Time

    This measures framework overhead including event processing, message parsing,
    evaluator work, and any other non-LLM/non-tool operations.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.task_start_time: Optional[float] = None
        self.task_end_time: Optional[float] = None

        # Track LLM time
        self.llm_start_time: Optional[float] = None
        self.total_llm_time: float = 0.0  # in seconds

        # Track Tool time
        self.tool_start_times: Dict[str, float] = {}  # tool_name -> start_time
        self.total_tool_time: float = 0.0  # in seconds

    def get_name(self) -> str:
        return "processing_overhead_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.TASK_START:
            self.task_start_time = timestamp
            self.logger.debug(f"Task started at {timestamp}")

        elif event_type == AgentEvent.TASK_END:
            self.task_end_time = timestamp
            self.logger.debug(f"Task ended at {timestamp}")

        elif event_type == AgentEvent.LLM_QUERY_START:
            self.llm_start_time = timestamp

        elif event_type == AgentEvent.LLM_QUERY_END:
            if self.llm_start_time is not None and timestamp is not None:
                status = data.get('status')
                if status == 'success':
                    llm_duration = timestamp - self.llm_start_time
                    self.total_llm_time += llm_duration
                    self.logger.debug(f"LLM call took {llm_duration:.3f}s, total LLM time: {self.total_llm_time:.3f}s")
                self.llm_start_time = None

        elif event_type == AgentEvent.TOOL_CALL_START:
            tool_name = data.get('tool_name', 'unknown')
            # Use unique key in case same tool is called multiple times concurrently
            call_id = f"{tool_name}_{timestamp}"
            self.tool_start_times[call_id] = timestamp

        elif event_type == AgentEvent.TOOL_CALL_END:
            tool_name = data.get('tool_name', 'unknown')
            # Find matching start time (most recent for this tool)
            matching_key = None
            for key in self.tool_start_times.keys():
                if key.startswith(f"{tool_name}_"):
                    matching_key = key
                    break

            if matching_key and timestamp is not None:
                start_time = self.tool_start_times.pop(matching_key)
                tool_duration = timestamp - start_time
                self.total_tool_time += tool_duration
                self.logger.debug(f"Tool '{tool_name}' took {tool_duration:.3f}s, total tool time: {self.total_tool_time:.3f}s")

    def get_value(self) -> Dict[str, Any]:
        if self.task_start_time is None or self.task_end_time is None:
            return {
                "processing_overhead_ms": None,
                "total_task_time_ms": None,
                "total_llm_time_ms": None,
                "total_tool_time_ms": None,
                "overhead_percentage": None
            }

        total_task_time = self.task_end_time - self.task_start_time
        processing_overhead = total_task_time - self.total_llm_time - self.total_tool_time

        # Calculate percentage of total time spent on overhead
        overhead_percentage = (processing_overhead / total_task_time * 100) if total_task_time > 0 else 0

        return {
            "processing_overhead_ms": round(processing_overhead * 1000, 2),
            "total_task_time_ms": round(total_task_time * 1000, 2),
            "total_llm_time_ms": round(self.total_llm_time * 1000, 2),
            "total_tool_time_ms": round(self.total_tool_time * 1000, 2),
            "overhead_percentage": round(overhead_percentage, 2)
        }

    def reset(self) -> None:
        super().reset()
        self.task_start_time = None
        self.task_end_time = None
        self.llm_start_time = None
        self.total_llm_time = 0.0
        self.tool_start_times = {}
        self.total_tool_time = 0.0
