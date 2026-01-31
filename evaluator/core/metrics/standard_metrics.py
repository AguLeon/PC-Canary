# evaluator/metrics/standard_metrics.py
import time
from typing import Dict, Any, Optional, List, Tuple
import logging

from collections import defaultdict
from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent

# TODO: This implementation requires passing Event instance and data for each member variable update, and data needs to be standardized. May need a simpler interface.
class TotalTimeMetric(BaseMetric):
    """Metric for calculating total task duration."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.task_start_time: Optional[float] = None
        self.task_end_time: Optional[float] = None

    def get_name(self) -> str:
        return "total_duration_seconds"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp', time.time())

        if event_type == AgentEvent.TASK_START:
            if self.task_start_time is None:
                self.task_start_time = timestamp
                self.logger.debug(f"Recorded task start time: {self.task_start_time}")
        elif event_type == AgentEvent.TASK_END:
             # Record last TASK_END as end time
             self.task_end_time = timestamp
             self.logger.debug(f"Recorded task end time: {self.task_end_time}")

    def get_value(self) -> Optional[float]:
        if self.task_start_time is not None and self.task_end_time is not None:
            duration = self.task_end_time - self.task_start_time
            return round(duration, 3)
        self.logger.warning(f"Cannot calculate total duration, start: {self.task_start_time}, end: {self.task_end_time}")
        return None

    def reset(self) -> None:
        super().reset()
        self.task_start_time = None
        self.task_end_time = None

class LLMCallCounterMetric(BaseMetric):
    """Metric for counting LLM API calls."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.call_count = 0

    def get_name(self) -> str:
        return "llm_call_count"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        if event_type == AgentEvent.LLM_QUERY_START: # Count at request start
            self.call_count += 1
            self.logger.debug(f"LLM call count increased: {self.call_count}")

    def get_value(self) -> int:
        return self.call_count

    def reset(self) -> None:
        super().reset()
        self.call_count = 0

class TokenCounterMetric(BaseMetric):
    """Metric for tracking LLM token consumption."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def get_name(self) -> str:
        return "llm_token_usage"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        # TODO: This implementation implies data format may vary, may need standardized format design
        if event_type == AgentEvent.LLM_QUERY_END and data.get('status') == 'success':
            prompt_tokens = data.get('prompt_tokens', 0)
            completion_tokens = data.get('completion_tokens', 0)
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens = self.total_prompt_tokens + self.total_completion_tokens
                self.logger.debug(f"Token accumulation: Prompt={self.total_prompt_tokens}, Completion={self.total_completion_tokens}, Total={self.total_tokens}")
            else:
                self.logger.warning(f"LLM_QUERY_END event missing valid token data: {data}")

    def get_value(self) -> Dict[str, int]:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def reset(self) -> None:
        super().reset()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

class TaskCompletionStatusMetric(BaseMetric):
    """
    Base metric for recording final task completion status.
    Primarily relies on TASK_END event. Task-specific success/failure determination
    should be handled by subclasses or other metrics listening to APP_SPECIFIC_EVENT,
    ultimately affecting the TASK_END status.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.status = "unknown"
        self.reason = ""

    def get_name(self) -> str:
        return "task_completion_status"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        if event_type == AgentEvent.TASK_END:
            task_status = data.get('status', 'failure') # Default to failure unless explicitly success or timeout
            self.status = task_status
            self.reason = data.get('reason', '')
            self.logger.info(f"Recorded final task status: {self.status}, reason: {self.reason}")

    def get_value(self) -> Dict[str, str]:
        return {"status": self.status, "reason": self.reason}

    def reset(self) -> None:
        super().reset()
        self.status = "unknown"
        self.reason = ""

class AgentSelfReportedCompletionMetric(BaseMetric):
    """Records whether the Agent believes it has completed the task."""
    # TODO: This may require modifying the original computer use prompt to design an agent self-report mechanism
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.agent_reported_completion = False
        self.reasoning = None

    def get_name(self) -> str:
        return "agent_reported_completion"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        if event_type == AgentEvent.AGENT_REPORTED_COMPLETION:
            self.agent_reported_completion = True
            self.reasoning = data.get('reasoning')
            self.logger.info(f"Agent reported task completion. Reasoning: {self.reasoning}")
        elif event_type == AgentEvent.STEP_END and data.get('agent_believes_completed'):
             self.agent_reported_completion = True
             self.reasoning = data.get('reasoning', 'Indicated in STEP_END')
             self.logger.info(f"Agent indicated task completion at step end.")


    def get_value(self) -> Dict[str, Any]:
        return {
            "completed": self.agent_reported_completion,
            "reasoning": self.reasoning
            }

    def reset(self) -> None:
        super().reset()
        self.agent_reported_completion = False
        self.reasoning = None

class ToolUsageMetric(BaseMetric):
    """Metric for tracking tool usage including call counts, success/failure, arguments, and errors."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        # Storage structure: {tool_name: {'calls': [], 'total_count': 0, 'success_count': 0, 'failure_count': 0}}
        self.tool_stats = defaultdict(lambda: {
            'calls': [],
            'total_count': 0,
            'success_count': 0,
            'failure_count': 0
        })
        self.total_tool_calls = 0

    def get_name(self) -> str:
        return "tool_usage_stats"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.TOOL_CALL_START:
            tool_name = data.get('tool_name')
            args = data.get('args')
            if tool_name:
                self.tool_stats[tool_name]['calls'].append({
                    'start_time': timestamp,
                    'args': args,
                    'end_time': None,
                    'success': None,
                    'result': None,
                    'error': None
                })
                self.tool_stats[tool_name]['total_count'] += 1
                self.total_tool_calls += 1
                self.logger.debug(f"Tool call started: {tool_name}, Args: {args}")
            else:
                self.logger.warning(f"TOOL_CALL_START event missing tool_name: {data}")

        elif event_type == AgentEvent.TOOL_CALL_END:
            tool_name = data.get('tool_name')
            success = data.get('success')
            result = data.get('result')
            error = data.get('error')

            if tool_name and tool_name in self.tool_stats:
                 # Find and update the corresponding 'start' call
                 # Assumes calls are sequential, updates the last incomplete call
                 call_list = self.tool_stats[tool_name]['calls']
                 if call_list and call_list[-1]['end_time'] is None:
                     last_call = call_list[-1]
                     last_call.update({
                         'end_time': timestamp,
                         'success': success,
                         'result': result,
                         'error': error
                     })

                     if success:
                         self.tool_stats[tool_name]['success_count'] += 1
                         self.logger.debug(f"Tool call succeeded: {tool_name}")
                     else:
                         self.tool_stats[tool_name]['failure_count'] += 1
                         self.logger.warning(f"Tool call failed: {tool_name}, Error: {error}")
                 else:
                    self.logger.error(f"Received TOOL_CALL_END but no matching start event found or call already ended: {tool_name}")

            elif tool_name:
                 self.logger.error(f"Received TOOL_CALL_END but start event was not recorded for tool: {tool_name}")
            else:
                self.logger.warning(f"TOOL_CALL_END event missing tool_name: {data}")


    def get_value(self) -> Dict[str, Any]:
        # Return processed statistics, can exclude raw calls list to simplify output
        summary = {
            "total_tool_calls": self.total_tool_calls,
            "tools": {}
        }
        for name, stats in self.tool_stats.items():
            summary["tools"][name] = {
                "total_count": stats['total_count'],
                "success_count": stats['success_count'],
                "failure_count": stats['failure_count'],
                # Optionally add last call information
                "last_call": stats['calls'][-1] if stats['calls'] else None
            }
        return summary

    def reset(self) -> None:
        super().reset()
        self.tool_stats = defaultdict(lambda: {
            'calls': [], 'total_count': 0, 'success_count': 0, 'failure_count': 0
        })
        self.total_tool_calls = 0
