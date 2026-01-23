# evaluator/core/result_collector.py
import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Type
from collections import defaultdict

# Core dependencies
from evaluator.core.events import AgentEvent
from evaluator.core.metrics.base_metrics import BaseMetric

# Import standard and task-specific metric classes to register
from evaluator.core.metrics.standard_metrics import (
    TotalTimeMetric,
    LLMCallCounterMetric,
    TokenCounterMetric,
    TaskCompletionStatusMetric,
    AgentSelfReportedCompletionMetric,
    ToolUsageMetric
)

from evaluator.core.metrics.error_metrics import ErrorCounterMetric
from evaluator.core.metrics.keystep_metrics import KeyStepMetric
from evaluator.core.metrics.ttft_metrics import TTFTMetric
from evaluator.core.metrics.cost_metrics import CostPerTurnMetric
from evaluator.core.metrics.generation_time_metrics import GenerationTimeMetric
from evaluator.core.metrics.overhead_metrics import ProcessingOverheadMetric
from evaluator.core.metrics.token_efficiency_metrics import TokenEfficiencyMetric


class ResultCollector:
    """
    Result Collector V2:
    Responsible for collecting raw event streams, managing metric calculator instances,
    distributing events, and aggregating and saving final results at the end of evaluation.
    """

    def __init__(self,
                 output_dir: str = "results",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the result collector.

        Args:
            output_dir: Result output directory.
            logger: Logger instance.
        """
        self.output_dir = output_dir
        # Main data structure: task_id -> {metadata, raw_events, computed_metrics}
        self.results: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "metadata": {},
            "raw_events": [],
            "computed_metrics": {}
        })
        self.logger = logger if logger else logging.getLogger(self.__class__.__name__)

        # Hold registered metric instances for each task: task_id -> List[BaseMetric]
        self.registered_metrics: Dict[str, List[BaseMetric]] = defaultdict(list)

        os.makedirs(output_dir, exist_ok=True)
        self.logger.info(f"Result collector initialized, results will be saved to: {output_dir}")

    def _register_metrics_for_task(self, task_id: str, task_config: Dict[str, Any]):
        """
        Register default and task-specific metric instances for the specified task.
        Only called during initial task configuration (e.g., in start_session).

        Args:
            task_id: Task ID for which to register metrics.
            task_config: Configuration dictionary for this task, used to initialize specific metrics.
        """
        if task_id in self.registered_metrics and self.registered_metrics[task_id]:
            self.logger.warning(f"Metrics for task {task_id} already registered, skipping.")
            return

        metrics_to_register: List[BaseMetric] = []
        self.logger.info(f"Starting metric registration for task {task_id}...")

        # --- 1. Register standard metrics ---
        standard_metric_classes: List[Type[BaseMetric]] = [
            TotalTimeMetric,
            LLMCallCounterMetric,
            TokenCounterMetric,
            TaskCompletionStatusMetric,
            AgentSelfReportedCompletionMetric,
            ToolUsageMetric,
            ErrorCounterMetric,
            TTFTMetric,
            CostPerTurnMetric,
            GenerationTimeMetric,
            ProcessingOverheadMetric,
            TokenEfficiencyMetric,
        ]
        for metric_cls in standard_metric_classes:
            try:
                # Pass logger to metric instance
                instance = metric_cls(logger=self.logger.getChild(metric_cls.__name__))
                metrics_to_register.append(instance)
                self.logger.debug(f"Registered standard metric: {instance.get_name()} for task {task_id}")
            except Exception as e:
                self.logger.error(f"Failed to register standard metric {metric_cls.__name__} (task {task_id}): {e}", exc_info=True)

        # --- 2. Register task-specific metrics (example: KeyStepMetric) ---
        # Get total number of steps
        total_steps = task_config.get('total_key_steps', 0)

        if isinstance(total_steps, int) and total_steps > 0:
            # Build step_names mapping
            parsed_step_names = {}
            event_configs = task_config.get('events', {})
            if isinstance(event_configs, dict):
                for event_name, event_config in event_configs.items():
                    if isinstance(event_config, dict) and event_config.get('is_key_step'):
                        idx = event_config.get('key_step_index')
                        name = event_config.get('key_step_name')
                        if isinstance(idx, int) and idx > 0 and isinstance(name, str):
                            if idx not in parsed_step_names: # Prevent duplicates (though BaseEvaluator also checks)
                                parsed_step_names[idx] = name
                            else:
                                self.logger.warning(f"Task {task_id} config has duplicate key step index {idx} in events, using first name '{parsed_step_names[idx]}'")

            if not parsed_step_names:
                self.logger.warning(f"When registering KeyStepMetric for task {task_id}, no valid key_step definitions found in events config.")
            # Even without step_names, KeyStepMetric can still be registered as long as total_steps is valid
            elif len(parsed_step_names) != total_steps:
                self.logger.warning(f"When registering KeyStepMetric for task {task_id}, configured total_key_steps ({total_steps}) does not match the number of key_steps defined in events ({len(parsed_step_names)}).")

            try:
                instance = KeyStepMetric(
                    total_steps=total_steps,
                    step_names=parsed_step_names, # Use mapping parsed from events
                    logger=self.logger.getChild(KeyStepMetric.__name__)
                )
                metrics_to_register.append(instance)
                self.logger.debug(f"Registered task-specific metric: {instance.get_name()} for task {task_id} (Total Steps: {total_steps}, Names: {parsed_step_names})")
            except ValueError as ve:
                self.logger.error(f"Failed to register KeyStepMetric (task {task_id}): {ve}")
            except Exception as e:
                self.logger.error(f"Unknown error occurred while registering KeyStepMetric (task {task_id}): {e}", exc_info=True)
        else:
            self.logger.info(f"Valid total_key_steps > 0 not found in task {task_id} config, skipping KeyStepMetric registration.")

        # --- (Can add more logic for loading new specific metrics based on config) ---
        # Example: if task_config.get('requires_custom_metric_X'): register CustomMetricX(...)

        self.registered_metrics[task_id] = metrics_to_register
        self.logger.info(f"Metric registration for task {task_id} complete, total of {len(metrics_to_register)} metrics.")


    def start_session(self, task_id: str, session_data: Dict[str, Any], task_config: Dict[str, Any]) -> None:
        """
        Start an evaluation session, register metrics and record metadata.

        Args:
            task_id: Task ID.
            session_data: Initial session metadata (e.g., app_path, pid).
            task_config: Complete configuration dictionary for this task.
        """
        # Ensure metrics are registered for this task (if not already registered)
        self._register_metrics_for_task(task_id, task_config)

        # Initialize or reset result structure (if previously run)
        self.results[task_id] = {
            "metadata": {},
            "raw_events": [],
            "computed_metrics": {}
        }
        # Reset metric state for this task
        self.reset_metrics(task_id)

        now = time.time()
        self.results[task_id]['metadata'] = {
            "session_start_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
            "session_start_unix": now,
            "task_config_at_start": task_config, # Store task config snapshot
            **session_data # Merge in passed metadata
        }

        self.logger.info(f"Task session started: {task_id}")


    def record_event(self, task_id: str, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        """
        Record a standardized AgentEvent and distribute it to registered metric handlers for this task.

        Args:
            task_id: Task ID.
            event_type: Event type (AgentEvent enum member).
            data: Event-related data (should contain 'timestamp').
        """
        # Ensure timestamp exists (BaseEvaluator should also do this check)
        if 'timestamp' not in data:
            data['timestamp'] = time.time()

        # --- 1. Store raw event ---
        # Add event type name for easier reading of raw logs
        raw_event_entry = {
            'event_type': event_type.name,
            **data
        }
        # No need to check if key exists after using defaultdict
        self.results[task_id]['raw_events'].append(raw_event_entry)
        # Reduce log redundancy, only record detailed data at DEBUG level
        self.logger.debug(f"Recorded raw event: {task_id} - {event_type.name} - {data if self.logger.isEnabledFor(logging.DEBUG) else '...'}")

        # --- 2. Distribute to metric handlers ---
        if task_id in self.registered_metrics:
            for metric in self.registered_metrics[task_id]:
                try:
                    # Each metric handles whether it cares about this event
                    metric.process_event(event_type, data)
                except Exception as e:
                    # Log error but continue processing other metrics
                    self.logger.error(f"Error while metric {metric.get_name()} was processing event {event_type.name} (task {task_id}): {e}", exc_info=True)
        else:
            # This should not normally happen since start_session registers metrics
            self.logger.warning(f"Task {task_id} has no registered metrics, cannot distribute event {event_type.name}.")


    def finalize_results(self, task_id: str) -> None:
        """
        At evaluation end, calculate final values for all registered metrics.
        This method should be explicitly called inside or before end_session.
        """
        if task_id not in self.results:
            self.logger.error(f"Cannot finalize results, result structure for task {task_id} does not exist.")
            return

        self.logger.info(f"Starting final metric calculation for task {task_id}...")
        computed_metrics: Dict[str, Any] = {}

        if task_id in self.registered_metrics:
            for metric in self.registered_metrics[task_id]:
                metric_name = metric.get_name()
                try:
                    metric_value = metric.get_value()
                    computed_metrics[metric_name] = metric_value
                    # Reduce log redundancy, only record each value at DEBUG level
                    self.logger.debug(f"Metric calculation complete ({task_id}): {metric_name} = {metric_value if self.logger.isEnabledFor(logging.DEBUG) else '...'}")
                except Exception as e:
                    self.logger.error(f"Error getting value for metric {metric_name} (task {task_id}): {e}", exc_info=True)
                    computed_metrics[metric_name] = f"ERROR_GETTING_VALUE: {e}" # Record error in results
        else:
             self.logger.warning(f"Task {task_id} has no registered metrics, cannot calculate final values.")

        # Store calculated metrics in result structure
        self.results[task_id]['computed_metrics'] = computed_metrics
        self.logger.info(f"Final metric calculation for task {task_id} complete.")


    def end_session(self, task_id: str, session_data: Dict[str, Any] = None) -> None:
        """
        End an evaluation session, calculate final metrics and record end time.

        Args:
            task_id: Task ID.
            session_data: Metadata to supplement at session end (optional).
        """
        if task_id not in self.results:
            self.logger.error(f"Cannot end session, task {task_id} does not exist or was not started.")
            return

        # --- 1. Ensure final metrics are calculated ---
        self.finalize_results(task_id)

        # --- 2. Record end time and total duration ---
        now = time.time()
        metadata = self.results[task_id]['metadata']
        metadata["session_end_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now))
        metadata["session_end_unix"] = now

        start_time = metadata.get("session_start_unix")
        duration = None
        if start_time:
            duration = round(now - start_time, 3)
            metadata["session_duration_seconds"] = duration

        # Merge any additional end session data
        if session_data:
             metadata.update(session_data)

        self.logger.info(f"Task session ended: {task_id}. Total duration: {duration if duration is not None else 'N/A'} seconds")


    def get_results(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get evaluation results for specified task or all tasks.

        Args:
            task_id: Task ID, returns all task results if None.

        Returns:
            Evaluation results dictionary.
        """
        if task_id is not None:
            # Return deep copy to prevent external modification of internal state? May impact performance for large results
            # import copy; return copy.deepcopy(self.results.get(task_id, {}))
            return self.results.get(task_id, {})
        # import copy; return copy.deepcopy(dict(self.results)) # Return copy of all results
        return dict(self.results) # Return shallow copy

    def get_current_metrics(self, task_id: str) -> Dict[str, Any]:
        """
        Get values (snapshot) of all currently registered metrics for specified task.
        This does not end the session, nor does it store results in final computed_metrics.
        Used to check intermediate state during evaluation.

        Args:
            task_id: Task ID.

        Returns:
            A dictionary containing current calculated metric names and values.
            Returns empty dictionary if task ID is invalid or has no registered metrics.
        """
        if task_id not in self.registered_metrics or not self.registered_metrics[task_id]:
            self.logger.warning(f"Failed to get current metrics, task {task_id} does not exist or has no registered metrics.")
            return {}

        self.logger.debug(f"Starting current metric snapshot calculation for task {task_id}...")
        current_metrics: Dict[str, Any] = {}

        for metric in self.registered_metrics[task_id]:
            metric_name = metric.get_name()
            try:
                metric_value = metric.get_value()
                current_metrics[metric_name] = metric_value
                # Reduce log redundancy, only record each value at DEBUG level
                self.logger.debug(f"Current metric calculation ({task_id}): {metric_name} = {metric_value if self.logger.isEnabledFor(logging.DEBUG) else '...'}")
            except Exception as e:
                self.logger.error(f"Error getting current value for metric {metric_name} (task {task_id}): {e}", exc_info=True)
                current_metrics[metric_name] = f"ERROR_GETTING_VALUE: {e}" # Record error in results

        self.logger.debug(f"Current metric snapshot calculation for task {task_id} complete.")
        return current_metrics

    def save_results(self, task_id: Optional[str] = None, filename_prefix: str = "result") -> str:
        """
        Save evaluation results to JSON file.

        Args:
            task_id: Task ID, saves all task results to single file if None.
            filename_prefix: Generated filename prefix.

        Returns:
            Result file path, returns empty string if failed.
        """
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        file_path = ""

        try:
            if task_id is not None:
                if task_id not in self.results:
                    self.logger.warning(f"Cannot save results, results for task {task_id} do not exist.")
                    return ""
                file_path = os.path.join(self.output_dir, f"{filename_prefix}_{task_id}_{timestamp_str}.json")
                data_to_save = self.results[task_id]
                log_msg = f"Results for task {task_id} saved: {file_path}"
            else:
                file_path = os.path.join(self.output_dir, f"{filename_prefix}_all_{timestamp_str}.json")
                data_to_save = dict(self.results) # Save snapshot of all results
                log_msg = f"All task results saved: {file_path}"

            with open(file_path, 'w', encoding='utf-8') as f:
                # Use default=str to handle non-serializable types (e.g., Enum members if they end up in data)
                json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)

            self.logger.info(log_msg)
            return file_path
        except TypeError as te:
             self.logger.error(f"Serialization error occurred while saving results to {file_path}: {te}. Ensure metric get_value() returns JSON-compatible types.", exc_info=True)
             return ""
        except Exception as e:
            self.logger.error(f"Failed to save results to {file_path}: {e}", exc_info=True)
            return ""


    def clear_results(self, task_id: Optional[str] = None) -> None:
        """
        Clear evaluation results and metric instances for specified task or all tasks from memory.

        Args:
            task_id: Task ID, clears all results if None.
        """
        tasks_to_clear = [task_id] if task_id and task_id in self.results else list(self.results.keys()) if task_id is None else []

        if not tasks_to_clear and task_id:
             self.logger.warning(f"Attempted to clear results for non-existent task: {task_id}")
             return
        elif not tasks_to_clear and task_id is None:
            self.logger.info("No results to clear.")
            return

        for tid in tasks_to_clear:
            if tid in self.results:
                del self.results[tid]
            if tid in self.registered_metrics:
                del self.registered_metrics[tid]
            self.logger.info(f"Cleared results and metric instances for task {tid}.")

        if task_id is None:
             self.logger.info("Cleared all evaluation results and metric instances.")


    def reset_metrics(self, task_id: Optional[str] = None) -> None:
        """
        Reset internal state of all registered metrics for specified task or all tasks.
        Used to run new evaluation round without recreating collector.

        Args:
            task_id: Task ID, resets metrics for all tasks if None.
        """
        tasks_to_reset = [task_id] if task_id and task_id in self.registered_metrics else list(self.registered_metrics.keys()) if task_id is None else []

        if not tasks_to_reset and task_id:
             self.logger.warning(f"Attempted to reset metrics for non-existent task: {task_id}")
             return
        elif not tasks_to_reset and task_id is None:
            self.logger.info("No metrics to reset.")
            return

        for tid in tasks_to_reset:
            self.logger.info(f"Resetting metric state for task {tid}...")
            metric_count = 0
            for metric in self.registered_metrics[tid]:
                try:
                    metric.reset()
                    metric_count += 1
                except Exception as e:
                    self.logger.error(f"Error resetting metric {metric.get_name()} (task {tid}): {e}", exc_info=True)
            self.logger.info(f"{metric_count} metrics for task {tid} have been reset.")
            # Also clear previous run's calculated results and raw events after reset
            if tid in self.results:
                self.results[tid]['raw_events'] = []
                self.results[tid]['computed_metrics'] = {}