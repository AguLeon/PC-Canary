# evaluator/core/result_collector.py
import csv
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
    ToolUsageMetric,
)

from evaluator.core.metrics.error_metrics import ErrorCounterMetric
from evaluator.core.metrics.keystep_metrics import KeyStepMetric
from evaluator.core.metrics.ttft_metrics import TTFTMetric
from evaluator.core.metrics.cost_metrics import CostPerTurnMetric
from evaluator.core.metrics.generation_time_metrics import GenerationTimeMetric
from evaluator.core.metrics.overhead_metrics import ProcessingOverheadMetric
from evaluator.core.metrics.token_efficiency_metrics import TokenEfficiencyMetric
from evaluator.core.metrics.tool_hallucination_metrics import ToolHallucinationMetric
from evaluator.core.metrics.loop_detection_metrics import LoopDetectionMetric
from evaluator.core.metrics.throughput_metrics import ThroughputMetric
from evaluator.core.metrics.tool_confidence_metrics import ToolConfidenceMetric


def _parse_gpu_metrics_csv(
    gpu_log_path: str,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parse a GPU metrics CSV file and compute aggregate statistics.

    If start_ts/end_ts are provided, only rows within that time window are used.
    This allows slicing a run-level GPU CSV to a specific task's duration.

    Returns a dict with avg/max/min for GPU utilization, VRAM, temperature,
    power draw, plus total energy consumption. Returns None if the file is
    missing, empty, or cannot be parsed.
    """
    if not os.path.exists(gpu_log_path):
        return None

    try:
        with open(gpu_log_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return None

        # Parse numeric columns, filtering by timestamp window if provided
        timestamps = []
        gpu_utils = []
        vrams = []
        temps = []
        powers = []
        cpu_pcts = []
        cpu_mems = []

        for row in rows:
            try:
                ts = float(row["timestamp"])
                if start_ts is not None and ts < start_ts:
                    continue
                if end_ts is not None and ts > end_ts:
                    continue
                timestamps.append(ts)
                # GPU columns may be empty on CPU-only hosts
                gpu_str = row.get("gpu_util_pct", "").strip()
                vram_str = row.get("vram_mb", "").strip()
                temp_str = row.get("temp_c", "").strip()
                power_str = row.get("power_w", "").strip()
                gpu_utils.append(float(gpu_str) if gpu_str else 0.0)
                vrams.append(float(vram_str) if vram_str else 0.0)
                temps.append(float(temp_str) if temp_str else 0.0)
                powers.append(float(power_str) if power_str else 0.0)
                # CPU columns are optional (backward compat with old CSVs)
                cpu_str = row.get("container_cpu_pct", "")
                mem_str = row.get("container_mem_mb", "")
                if cpu_str:
                    cpu_pcts.append(float(cpu_str))
                if mem_str:
                    cpu_mems.append(float(mem_str))
            except (ValueError, KeyError):
                continue

        if not timestamps:
            return None

        n = len(timestamps)

        # Calculate energy: sum(power_watts * time_interval)
        energy_joules = 0.0
        for i in range(1, n):
            dt = timestamps[i] - timestamps[i - 1]
            energy_joules += powers[i] * dt

        # Energy acceleration: break into halves (H1-H2) by sample count
        half = n // 2
        h_energy = [0.0, 0.0]
        h_duration = [0.0, 0.0]
        for i in range(1, n):
            dt = timestamps[i] - timestamps[i - 1]
            h = 0 if i <= half else 1
            h_energy[h] += powers[i] * dt
            h_duration[h] += dt
        h_rate = [
            round(h_energy[h] / h_duration[h], 2) if h_duration[h] > 0 else 0.0
            for h in range(2)
        ]
        energy_rate_ratio_h2_h1 = (
            round(h_rate[1] / h_rate[0], 4) if h_rate[0] > 0 else None
        )

        # Energy acceleration: break into quintiles (Q1-Q5) by sample count
        num_q = 5
        q_boundaries = [round(n * i / num_q) for i in range(num_q + 1)]
        q_energy = [0.0] * num_q
        q_duration = [0.0] * num_q
        for i in range(1, n):
            dt = timestamps[i] - timestamps[i - 1]
            for q in range(num_q):
                if q_boundaries[q] < i <= q_boundaries[q + 1]:
                    q_energy[q] += powers[i] * dt
                    q_duration[q] += dt
                    break

        q_rate = [
            round(q_energy[q] / q_duration[q], 2) if q_duration[q] > 0 else 0.0
            for q in range(num_q)
        ]
        # Ratio of Q4 avg power to Q2 avg power (skips Q1 startup and Q5 cooldown)
        energy_rate_ratio_q4_q2 = (
            round(q_rate[3] / q_rate[1], 4) if q_rate[1] > 0 else None
        )

        # VRAM usage: halves (H1-H2) by sample count
        vram_h = [[], []]
        for i in range(n):
            h = 0 if i < half else 1
            vram_h[h].append(vrams[i])
        vram_h_avg = [
            round(sum(v) / len(v), 2) if v else 0.0 for v in vram_h
        ]
        vram_ratio_h2_h1 = (
            round(vram_h_avg[1] / vram_h_avg[0], 4) if vram_h_avg[0] > 0 else None
        )

        # VRAM usage: quintiles (Q1-Q5) by sample count
        vram_q = [[] for _ in range(num_q)]
        for i in range(n):
            for q in range(num_q):
                if q_boundaries[q] <= i < q_boundaries[q + 1]:
                    vram_q[q].append(vrams[i])
                    break
        vram_q_avg = [
            round(sum(v) / len(v), 2) if v else 0.0 for v in vram_q
        ]
        vram_ratio_q4_q2 = (
            round(vram_q_avg[3] / vram_q_avg[1], 4) if vram_q_avg[1] > 0 else None
        )

        return {
            "avg_gpu_util_pct": round(sum(gpu_utils) / n, 2),
            "max_gpu_util_pct": round(max(gpu_utils), 2),
            "min_gpu_util_pct": round(min(gpu_utils), 2),
            "avg_vram_mb": round(sum(vrams) / n, 2),
            "peak_vram_mb": round(max(vrams), 2),
            "min_vram_mb": round(min(vrams), 2),
            "avg_temp_c": round(sum(temps) / n, 2),
            "max_temp_c": round(max(temps), 2),
            "avg_power_w": round(sum(powers) / n, 2),
            "max_power_w": round(max(powers), 2),
            "total_energy_joules": round(energy_joules, 2),
            "total_energy_kwh": round(energy_joules / 3_600_000, 8),
            "energy_h1_joules": round(h_energy[0], 2),
            "energy_h2_joules": round(h_energy[1], 2),
            "avg_power_h1_w": h_rate[0],
            "avg_power_h2_w": h_rate[1],
            "energy_rate_ratio_h2_h1": energy_rate_ratio_h2_h1,
            "energy_q1_joules": round(q_energy[0], 2),
            "energy_q2_joules": round(q_energy[1], 2),
            "energy_q3_joules": round(q_energy[2], 2),
            "energy_q4_joules": round(q_energy[3], 2),
            "energy_q5_joules": round(q_energy[4], 2),
            "avg_power_q1_w": q_rate[0],
            "avg_power_q2_w": q_rate[1],
            "avg_power_q3_w": q_rate[2],
            "avg_power_q4_w": q_rate[3],
            "avg_power_q5_w": q_rate[4],
            "energy_rate_ratio_q4_q2": energy_rate_ratio_q4_q2,
            "avg_vram_h1_mb": vram_h_avg[0],
            "avg_vram_h2_mb": vram_h_avg[1],
            "vram_ratio_h2_h1": vram_ratio_h2_h1,
            "avg_vram_q1_mb": vram_q_avg[0],
            "avg_vram_q2_mb": vram_q_avg[1],
            "avg_vram_q3_mb": vram_q_avg[2],
            "avg_vram_q4_mb": vram_q_avg[3],
            "avg_vram_q5_mb": vram_q_avg[4],
            "vram_ratio_q4_q2": vram_ratio_q4_q2,
            "sample_count": n,
            "monitoring_duration_sec": round(timestamps[-1] - timestamps[0], 2),
            "avg_container_cpu_pct": round(sum(cpu_pcts) / len(cpu_pcts), 2) if cpu_pcts else None,
            "max_container_cpu_pct": round(max(cpu_pcts), 2) if cpu_pcts else None,
            "avg_container_mem_mb": round(sum(cpu_mems) / len(cpu_mems), 2) if cpu_mems else None,
            "peak_container_mem_mb": round(max(cpu_mems), 2) if cpu_mems else None,
        }
    except Exception:
        return None


class ResultCollector:
    """
    Result Collector V2:
    Responsible for collecting raw event streams, managing metric calculator instances,
    distributing events, and aggregating and saving final results at the end of evaluation.
    """

    def __init__(
        self, output_dir: str = "results", logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the result collector.

        Args:
            output_dir: Result output directory.
            logger: Logger instance.
        """
        self.output_dir = output_dir
        # Main data structure: task_id -> {metadata, raw_events, computed_metrics}
        self.results: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"metadata": {}, "raw_events": [], "computed_metrics": {}}
        )
        self.logger = logger if logger else logging.getLogger(self.__class__.__name__)

        # Hold registered metric instances for each task: task_id -> List[BaseMetric]
        self.registered_metrics: Dict[str, List[BaseMetric]] = defaultdict(list)

        os.makedirs(output_dir, exist_ok=True)
        self.logger.info(
            f"Result collector initialized, results will be saved to: {output_dir}"
        )

    def _register_metrics_for_task(self, task_id: str, task_config: Dict[str, Any]):
        """
        Register default and task-specific metric instances for the specified task.
        Only called during initial task configuration (e.g., in start_session).

        Args:
            task_id: Task ID for which to register metrics.
            task_config: Configuration dictionary for this task, used to initialize specific metrics.
        """
        if task_id in self.registered_metrics and self.registered_metrics[task_id]:
            self.logger.warning(
                f"Metrics for task {task_id} already registered, skipping."
            )
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
            ToolHallucinationMetric,
            LoopDetectionMetric,
            ThroughputMetric,
            ToolConfidenceMetric,
        ]
        for metric_cls in standard_metric_classes:
            try:
                # Pass logger to metric instance
                instance = metric_cls(logger=self.logger.getChild(metric_cls.__name__))
                metrics_to_register.append(instance)
                self.logger.debug(
                    f"Registered standard metric: {instance.get_name()} for task {task_id}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to register standard metric {metric_cls.__name__} (task {task_id}): {e}",
                    exc_info=True,
                )

        # --- 2. Register task-specific metrics (example: KeyStepMetric) ---
        # Get total number of steps
        total_steps = task_config.get("total_key_steps", 0)

        if isinstance(total_steps, int) and total_steps > 0:
            # Build step_names mapping
            parsed_step_names = {}
            event_configs = task_config.get("events", {})
            if isinstance(event_configs, dict):
                for event_name, event_config in event_configs.items():
                    if isinstance(event_config, dict) and event_config.get(
                        "is_key_step"
                    ):
                        idx = event_config.get("key_step_index")
                        name = event_config.get("key_step_name")
                        if isinstance(idx, int) and idx > 0 and isinstance(name, str):
                            if (
                                idx not in parsed_step_names
                            ):  # Prevent duplicates (though BaseEvaluator also checks)
                                parsed_step_names[idx] = name
                            else:
                                self.logger.warning(
                                    f"Task {task_id} config has duplicate key step index {idx} in events, using first name '{parsed_step_names[idx]}'"
                                )

            if not parsed_step_names:
                self.logger.warning(
                    f"When registering KeyStepMetric for task {task_id}, no valid key_step definitions found in events config."
                )
            # Even without step_names, KeyStepMetric can still be registered as long as total_steps is valid
            elif len(parsed_step_names) != total_steps:
                self.logger.warning(
                    f"When registering KeyStepMetric for task {task_id}, configured total_key_steps ({total_steps}) does not match the number of key_steps defined in events ({len(parsed_step_names)})."
                )

            try:
                instance = KeyStepMetric(
                    total_steps=total_steps,
                    step_names=parsed_step_names,  # Use mapping parsed from events
                    logger=self.logger.getChild(KeyStepMetric.__name__),
                )
                metrics_to_register.append(instance)
                self.logger.debug(
                    f"Registered task-specific metric: {instance.get_name()} for task {task_id} (Total Steps: {total_steps}, Names: {parsed_step_names})"
                )
            except ValueError as ve:
                self.logger.error(
                    f"Failed to register KeyStepMetric (task {task_id}): {ve}"
                )
            except Exception as e:
                self.logger.error(
                    f"Unknown error occurred while registering KeyStepMetric (task {task_id}): {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Valid total_key_steps > 0 not found in task {task_id} config, skipping KeyStepMetric registration."
            )

        # --- (Can add more logic for loading new specific metrics based on config) ---
        # Example: if task_config.get('requires_custom_metric_X'): register CustomMetricX(...)

        self.registered_metrics[task_id] = metrics_to_register
        self.logger.info(
            f"Metric registration for task {task_id} complete, total of {len(metrics_to_register)} metrics."
        )

    def start_session(
        self, task_id: str, session_data: Dict[str, Any], task_config: Dict[str, Any]
    ) -> None:
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
            "computed_metrics": {},
        }
        # Reset metric state for this task
        self.reset_metrics(task_id)

        now = time.time()
        # Extract model info from environment
        model_name = os.environ.get("MODEL", "unknown")
        temperature: float | None = float(os.environ.get("LLM_temperature", 0.7))  # If not given, assume the default temperature is 0.7
        infrastructure_tag = os.environ.get("INFRASTRUCTURE_TAG", "")

        self.results[task_id]["metadata"] = {
            "session_start_iso": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.localtime(now)
            ),
            "session_start_unix": now,
            "model_name": model_name,  # Add model name
            "temperature": temperature,  # Add temperature
            "infrastructure_tag": infrastructure_tag,  # Add infrastructure tag
            "task_config_at_start": task_config,  # Store task config snapshot
            **session_data,  # Merge in passed metadata
        }

        self.logger.info(f"Task session started: {task_id}")

    def record_event(
        self, task_id: str, event_type: AgentEvent, data: Dict[str, Any]
    ) -> None:
        """
        Record a standardized AgentEvent and distribute it to registered metric handlers for this task.

        Args:
            task_id: Task ID.
            event_type: Event type (AgentEvent enum member).
            data: Event-related data (should contain 'timestamp').
        """
        # Ensure timestamp exists (BaseEvaluator should also do this check)
        if "timestamp" not in data:
            data["timestamp"] = time.time()

        # --- 1. Store raw event ---
        # Add event type name for easier reading of raw logs
        raw_event_entry = {"event_type": event_type.name, **data}
        # No need to check if key exists after using defaultdict
        self.results[task_id]["raw_events"].append(raw_event_entry)
        # Reduce log redundancy, only record detailed data at DEBUG level
        self.logger.debug(
            f"Recorded raw event: {task_id} - {event_type.name} - {data if self.logger.isEnabledFor(logging.DEBUG) else '...'}"
        )

        # --- 2. Distribute to metric handlers ---
        if task_id in self.registered_metrics:
            for metric in self.registered_metrics[task_id]:
                try:
                    # Each metric handles whether it cares about this event
                    metric.process_event(event_type, data)
                except Exception as e:
                    # Log error but continue processing other metrics
                    self.logger.error(
                        f"Error while metric {metric.get_name()} was processing event {event_type.name} (task {task_id}): {e}",
                        exc_info=True,
                    )
        else:
            # This should not normally happen since start_session registers metrics
            self.logger.warning(
                f"Task {task_id} has no registered metrics, cannot distribute event {event_type.name}."
            )

    def finalize_results(self, task_id: str) -> None:
        """
        At evaluation end, calculate final values for all registered metrics.
        This method should be explicitly called inside or before end_session.
        """
        if task_id not in self.results:
            self.logger.error(
                f"Cannot finalize results, result structure for task {task_id} does not exist."
            )
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
                    self.logger.debug(
                        f"Metric calculation complete ({task_id}): {metric_name} = {metric_value if self.logger.isEnabledFor(logging.DEBUG) else '...'}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error getting value for metric {metric_name} (task {task_id}): {e}",
                        exc_info=True,
                    )
                    computed_metrics[metric_name] = (
                        f"ERROR_GETTING_VALUE: {e}"  # Record error in results
                    )
        else:
            self.logger.warning(
                f"Task {task_id} has no registered metrics, cannot calculate final values."
            )

        # Store calculated metrics in result structure
        self.results[task_id]["computed_metrics"] = computed_metrics
        self.logger.info(f"Final metric calculation for task {task_id} complete.")

    def end_session(self, task_id: str, session_data: Dict[str, Any] = None) -> None:
        """
        End an evaluation session, calculate final metrics and record end time.

        Args:
            task_id: Task ID.
            session_data: Metadata to supplement at session end (optional).
        """
        if task_id not in self.results:
            self.logger.error(
                f"Cannot end session, task {task_id} does not exist or was not started."
            )
            return

        # --- 1. Ensure final metrics are calculated ---
        self.finalize_results(task_id)

        # --- 2. Record end time and total duration ---
        now = time.time()
        metadata = self.results[task_id]["metadata"]
        metadata["session_end_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S%z", time.localtime(now)
        )
        metadata["session_end_unix"] = now

        start_time = metadata.get("session_start_unix")
        duration = None
        if start_time:
            duration = round(now - start_time, 3)
            metadata["session_duration_seconds"] = duration

        # Merge any additional end session data
        if session_data:
            metadata.update(session_data)

        self.logger.info(
            f"Task session ended: {task_id}. Total duration: {duration if duration is not None else 'N/A'} seconds"
        )

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
        return dict(self.results)  # Return shallow copy

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
        if (
            task_id not in self.registered_metrics
            or not self.registered_metrics[task_id]
        ):
            self.logger.warning(
                f"Failed to get current metrics, task {task_id} does not exist or has no registered metrics."
            )
            return {}

        self.logger.debug(
            f"Starting current metric snapshot calculation for task {task_id}..."
        )
        current_metrics: Dict[str, Any] = {}

        for metric in self.registered_metrics[task_id]:
            metric_name = metric.get_name()
            try:
                metric_value = metric.get_value()
                current_metrics[metric_name] = metric_value
                # Reduce log redundancy, only record each value at DEBUG level
                self.logger.debug(
                    f"Current metric calculation ({task_id}): {metric_name} = {metric_value if self.logger.isEnabledFor(logging.DEBUG) else '...'}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error getting current value for metric {metric_name} (task {task_id}): {e}",
                    exc_info=True,
                )
                current_metrics[metric_name] = (
                    f"ERROR_GETTING_VALUE: {e}"  # Record error in results
                )

        self.logger.debug(
            f"Current metric snapshot calculation for task {task_id} complete."
        )
        return current_metrics

    def save_results(
        self, task_id: Optional[str] = None, filename_prefix: str = "result"
    ) -> str:
        """
        Save evaluation results to JSON file.

        Args:
            task_id: Task ID, saves all task results to single file if None.
            filename_prefix: Generated filename prefix.

        Returns:
            Result file path, returns empty string if failed.
        """
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        # Extract model name and infrastructure tag from environment
        model_name = os.environ.get("MODEL", "unknown").replace(":", "-").replace("/", "_")
        infrastructure_tag = os.environ.get("INFRASTRUCTURE_TAG", "")
        infrastructure_suffix = f"_{infrastructure_tag}" if infrastructure_tag else ""
        file_path = ""

        try:
            if task_id is not None:
                if task_id not in self.results:
                    self.logger.warning(
                        f"Cannot save results, results for task {task_id} do not exist."
                    )
                    return ""
                file_path = os.path.join(
                    self.output_dir,
                    f"{filename_prefix}_{timestamp_str}_{model_name}{infrastructure_suffix}_{task_id}.json",
                )
                data_to_save = self.results[task_id]
                log_msg = f"Results for task {task_id} saved: {file_path}"
            else:
                file_path = os.path.join(
                    self.output_dir,
                    f"{filename_prefix}_{timestamp_str}_{model_name}{infrastructure_suffix}_all.json",
                )
                data_to_save = dict(self.results)  # Save snapshot of all results
                log_msg = f"All task results saved: {file_path}"

            # Inject GPU hardware metrics if a matching CSV exists
            if task_id is not None:
                # Get task start/end timestamps for slicing the GPU CSV
                metadata = data_to_save.get("metadata", {})
                task_start = metadata.get("session_start_unix")
                task_end = metadata.get("session_end_unix")

                # Search for gpu_metrics_*.csv in output dir, ancestors,
                # and a gpu_logs/ subfolder under each ancestor
                search_dirs = [self.output_dir]
                parent = os.path.dirname(self.output_dir)
                if parent:
                    search_dirs.append(parent)
                    gpu_logs = os.path.join(parent, "gpu_logs")
                    if os.path.isdir(gpu_logs):
                        search_dirs.append(gpu_logs)
                grandparent = os.path.dirname(parent) if parent else None
                if grandparent:
                    search_dirs.append(grandparent)
                    gpu_logs = os.path.join(grandparent, "gpu_logs")
                    if os.path.isdir(gpu_logs):
                        search_dirs.append(gpu_logs)

                for search_dir in search_dirs:
                    if not os.path.isdir(search_dir):
                        continue
                    for fname in os.listdir(search_dir):
                        if fname.startswith("gpu_metrics_") and fname.endswith(".csv"):
                            gpu_csv_path = os.path.join(search_dir, fname)
                            gpu_metrics = _parse_gpu_metrics_csv(
                                gpu_csv_path,
                                start_ts=task_start,
                                end_ts=task_end,
                            )
                            if gpu_metrics:
                                data_to_save["gpu_hardware_metrics"] = gpu_metrics
                                self.logger.info(
                                    f"Added GPU hardware metrics from {fname} "
                                    f"({gpu_metrics['sample_count']} samples, "
                                    f"sliced to task window)"
                                )
                                break
                    if "gpu_hardware_metrics" in data_to_save:
                        break

            with open(file_path, "w", encoding="utf-8") as f:
                # Use default=str to handle non-serializable types (e.g., Enum members if they end up in data)
                json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)

            self.logger.info(log_msg)
            return file_path
        except TypeError as te:
            self.logger.error(
                f"Serialization error occurred while saving results to {file_path}: {te}. Ensure metric get_value() returns JSON-compatible types.",
                exc_info=True,
            )
            return ""
        except Exception as e:
            self.logger.error(
                f"Failed to save results to {file_path}: {e}", exc_info=True
            )
            return ""

    def clear_results(self, task_id: Optional[str] = None) -> None:
        """
        Clear evaluation results and metric instances for specified task or all tasks from memory.

        Args:
            task_id: Task ID, clears all results if None.
        """
        tasks_to_clear = (
            [task_id]
            if task_id and task_id in self.results
            else list(self.results.keys())
            if task_id is None
            else []
        )

        if not tasks_to_clear and task_id:
            self.logger.warning(
                f"Attempted to clear results for non-existent task: {task_id}"
            )
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
        tasks_to_reset = (
            [task_id]
            if task_id and task_id in self.registered_metrics
            else list(self.registered_metrics.keys())
            if task_id is None
            else []
        )

        if not tasks_to_reset and task_id:
            self.logger.warning(
                f"Attempted to reset metrics for non-existent task: {task_id}"
            )
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
                    self.logger.error(
                        f"Error resetting metric {metric.get_name()} (task {tid}): {e}",
                        exc_info=True,
                    )
            self.logger.info(f"{metric_count} metrics for task {tid} have been reset.")
            # Also clear previous run's calculated results and raw events after reset
            if tid in self.results:
                self.results[tid]["raw_events"] = []
                self.results[tid]["computed_metrics"] = {}

