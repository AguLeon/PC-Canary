import importlib
from typing import Dict, Any, List, Callable, Optional, Set
import os
import sys
import time
import json
import signal
import subprocess
import time
import logging
from string import Template

from evaluator.core.hook_manager import HookManager
from evaluator.core.ipc_injector import IpcInjector
from evaluator.core.state_inspector import StateInspector

from evaluator.core.result_collector import ResultCollector
from evaluator.core.events import AgentEvent
from evaluator.utils.logger import setup_logger
from evaluator.utils.restore_context_data import restore_context_data

# Data structure for completion callbacks


class CallbackEventData:
    def __init__(self, event_type: str, message: str, data: Dict[str, Any] = None):
        self.event_type = (
            event_type  # e.g., "task_completed", "task_error", "evaluator_stopped"
        )
        self.message = message
        self.data = data or {}


class BaseEvaluator:
    """
    Base evaluator class that defines a general evaluation workflow and interface.
    Can be extended by task-specific evaluators.
    """

    def __init__(
        self,
        task: Dict,
        log_dir: str = "logs",
        app_path: str = None,
        app_working_path=None,
        custom_params: Dict = None,
        **kwargs,
    ):
        """
        Initialize the base evaluator.

        Args:
            task: Task configuration dictionary
            log_dir: Directory to save logs and results
            app_path: Application path
            custom_params: Dictionary of custom parameters to override or supplement the configuration
            **kwargs: Other parameters
        """
        self.task_category = task["category"]
        self.task_id = task["id"]
        self.log_dir = log_dir
        self.session_id = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(log_dir, self.session_id)

        # Save custom parameters
        self.custom_params = custom_params or {}

        # Create session directory
        os.makedirs(self.session_dir, exist_ok=True)

        # Set up logger
        self.logger = setup_logger(
            f"{self.task_category}_{self.task_id}_evaluator",
            self.session_dir,
            level=logging.WARNING,
        )
        FILE_ROOT = os.path.dirname(os.path.abspath(__file__))
        self.canary_root = os.path.dirname(os.path.dirname(FILE_ROOT))
        self.task_path = os.path.join(
            self.canary_root, "tests/tasks", self.task_category, self.task_id
        )

        # Evaluation state
        self.is_running = False
        self.task_completed = False

        # Configuration and results
        self.config = {}
        self.workspace_targets: Set[str] = set()

        # Callback-related
        self.completion_callbacks: List[
            Callable[[CallbackEventData, "BaseEvaluator"], None]
        ] = []
        self._final_callback_triggered = False  # Internal flag
        self.message_handler: Optional[
            Callable[[Dict, Any], Optional[List[Dict[str, Any]]]]
        ] = None  # Expect list of dicts

        # Load configuration file and initialize self.instruction
        config_path = os.path.join(self.task_path, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as config_file:
                self.config = json.load(config_file)

                # Override or supplement configuration with custom_params
                if self.custom_params:
                    # Special handling for 'task_parameters'
                    if (
                        "task_parameters" in self.config
                        and "task_parameters" in self.custom_params
                    ):
                        for key, value in self.custom_params["task_parameters"].items():
                            if key in self.config["task_parameters"]:
                                old_value = self.config["task_parameters"][key]
                                self.config["task_parameters"][key] = value
                                self.logger.info(
                                    f"Updated task parameter: {key} = {value} (old value: {old_value})"
                                )
                            else:
                                self.logger.warning(
                                    f"Ignored unknown task parameter: {key} = {value}"
                                )

                    # Overwrite other top-level parameters
                    for key, value in self.custom_params.items():
                        if key != "task_parameters":
                            self.config[key] = value
                            self.logger.info(f"Custom parameter set: {key} = {value}")

                # Load and render instruction template with parameters
                raw_template = self.config.get(
                    "instruction_template", self.config.get("instruction", "")
                )
                params = self.config.get("task_parameters", {})
                try:
                    self.instruction = Template(raw_template).safe_substitute(params)
                except Exception as e:
                    self.logger.warning(
                        f"Instruction template substitution failed: {e}"
                    )
                    self.instruction = raw_template
                self.logger.info(f"Loaded task instruction: {self.instruction}")
        else:
            self.logger.warning(f"Configuration file not found: {config_path}")

        # Initialize key step information (just total count; name mapping handled by ResultCollector)
        self.total_key_steps = self.config.get("total_key_steps", 0)

        self.preconditions = self.config.get("preconditions", {})
        self.timeout = self.config.get("evaluation_setup", {}).get("timeout", 180)
        evaluate_on_completion = self.config.get("evaluation_setup", {}).get(
            "evaluate_on_completion", False
        )
        evaluator_type = self.config.get("evaluation_setup", {}).get(
            "evaluator_type", "HookManager"
        )
        launch_args = self.config.get("application_info", {}).get("args", [])
        app_working_cwd = self.config.get("application_info", {}).get("cwd", None)

        # If app_path not provided as parameter, read from config
        if app_path is None:
            app_path = self.config.get("application_info", {}).get("executable_path")

        # Initialize components with the shared logger
        if evaluator_type == "IpcInjector":
            self.hook_manager = IpcInjector(
                app_path=app_path,
                args=launch_args,
                logger=self.logger,
                evaluate_on_completion=evaluate_on_completion,
            )
        elif evaluator_type == "StateInspector":
            self.hook_manager = StateInspector(
                app_path=app_path,
                app_working_cwd=app_working_cwd,
                args=launch_args,
                logger=self.logger,
                evaluate_on_completion=evaluate_on_completion,
            )
        else:
            self.hook_manager = HookManager(
                app_path=app_path,
                app_working_cwd=app_working_cwd,
                args=launch_args,
                logger=self.logger,
                evaluate_on_completion=evaluate_on_completion,
            )

        # Initialize ResultCollector (needs to be before handler is set)
        self.result_collector = ResultCollector(
            output_dir=self.session_dir, logger=self.logger
        )
        if not (
            "evaluation_setup" in self.config
            and "scripts" in self.config["evaluation_setup"]
        ):
            raise RuntimeError("Missing evaluation_setup or scripts")

        for script in self.config["evaluation_setup"]["scripts"]:
            script_path = os.path.realpath(os.path.join(self.task_path, script["path"]))
            if not os.path.exists(script_path):
                raise RuntimeError("Script file does not exist")

            match script["role"]:
                case "hook":
                    dep_script_list = []
                    if "dependency" in script:
                        for dep in script["dependency"]:
                            dep_path = os.path.realpath(
                                os.path.join(self.task_path, dep)
                            )
                            if not os.path.exists(dep_path):
                                raise RuntimeError(
                                    "Hook dependency file does not exist"
                                )
                            dep_script_list.append(dep_path)
                    self.hook_manager.add_script(script_path, dep_script_list)
                case "handler":
                    self.set_message_handler(script_path)
        self.logger.info(f"Evaluator initialized: {self.task_id}")

    @property
    def default_instruction(self) -> str:
        """Return the loaded and rendered task instruction"""
        return getattr(self, "instruction", "")  # Safe fallback

    def record_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        """
        Record a standardized AgentEvent.

        Args:
            event_type: Event type (AgentEvent enum member)
            data: Event-related data
        """
        if "timestamp" not in data:
            data["timestamp"] = time.time()

        self.result_collector.record_event(self.task_id, event_type, data)
        # Reduce redundant logging; debug level controlled by ResultCollector
        # self.logger.debug(f"Recorded event: {event_type.name} - {data}")

    def set_message_handler(self, module_path) -> None:
        # Attempt to import the corresponding handler module
        try:
            if os.path.exists(module_path):
                spec = importlib.util.spec_from_file_location("handler", module_path)
                handler_module = importlib.util.module_from_spec(spec)
                sys.modules["handler"] = handler_module
                spec.loader.exec_module(handler_module)

                if hasattr(handler_module, "register_handlers"):
                    self.message_handler = handler_module.register_handlers(self)
                    self.logger.info(
                        f"Successfully set callback: {module_path}.register_handlers"
                    )
                elif hasattr(handler_module, "message_handler"):
                    self.message_handler = handler_module.message_handler
                    self.logger.info(
                        f"Successfully set callback: {module_path}.message_handler"
                    )
                else:
                    self.logger.warning(f"No callback function found in: {module_path}")
            else:
                self.logger.warning(f"Callback file does not exist: {module_path}")
            except Exception as e:
                self.logger.error(f"Failed to import callback module: {str(e)}")

    def _on_message(self, message: Dict[str, Any], data: Any) -> None:
        """
        Internal message handler, called by HookManager.
        Calls the task-specific message_handler and updates events based on returned status.

        Args:
            message: Message object (usually from scripts)
            data: Additional data
        """
        if not self.message_handler:
            return

        try:
            # Call handler, expecting Optional[List[Dict[str, Any]]]
            handler_updates = self.message_handler(
                message, self.logger, self.config.get("task_parameters", {})
            )
        except Exception as e:
            self.logger.error(f"Error executing message_handler: {e}", exc_info=True)
            # Record error and trigger callbacks
            error_reason = f"Handler execution error: {e}"
            current_time = time.time()
            self.record_event(
                AgentEvent.AGENT_ERROR_OCCURRED,
                {
                    "timestamp": current_time,
                    "error": "Handler Exception",
                    "message": str(e),
                },
            )
            self.record_event(
                AgentEvent.TASK_END,
                {
                    "timestamp": current_time,
                    "status": "failure",
                    "reason": error_reason,
                },
            )
            # Trigger callback and set final flag
            self._trigger_completion_callbacks(
                CallbackEventData("task_error", error_reason)
            )
            self._final_callback_triggered = True
            return

        if handler_updates is None or not isinstance(handler_updates, list):
            # Handler returned None or invalid type, no important updates
            return

        current_time = (
            time.time()
        )  # Use consistent timestamp for events from this handler call

        for update in handler_updates:
            if not isinstance(update, dict):
                self.logger.warning(f"Handler returned invalid item in list: {update}")
                continue

            status = update.get("status")

            # Process based on handler status
            match status:
                case "success":
                    reason = update.get("reason", "Handler reported success")
                    self.logger.info(f"Handler reported success: {reason}")
                    # Record TASK_END event
                    self.record_event(
                        AgentEvent.TASK_END,
                        {
                            "timestamp": current_time,
                            "status": "success",
                            "reason": reason,
                        },
                    )
                    # Trigger success callback
                    self._trigger_completion_callbacks(
                        CallbackEventData("task_completed", reason)
                    )

                case "error":
                    error_type = update.get("type", "handler_error")
                    error_message = update.get("message", "Handler reported error")
                    stack_trace = update.get("stack_trace")
                    error_reason = f"{error_type}: {error_message}"
                    self.logger.error(f"Handler reported error: {error_reason}")
                    # Record AGENT_ERROR_OCCURRED
                    error_data = {
                        "timestamp": current_time,
                        "error": error_type,
                        "message": error_message,
                    }
                    if stack_trace:
                        error_data["stack_trace"] = stack_trace
                    self.record_event(AgentEvent.AGENT_ERROR_OCCURRED, error_data)
                    # Record TASK_END event
                    self.record_event(
                        AgentEvent.TASK_END,
                        {
                            "timestamp": current_time,
                            "status": "failure",
                            "reason": error_reason,
                        },
                    )
                    # Trigger error callback
                    self._trigger_completion_callbacks(
                        CallbackEventData("task_error", error_reason)
                    )

                case "key_step":
                    step_index = update.get("index")
                    name_from_handler = update.get(
                        "name"
                    )  # Handler can override default name

                    if not isinstance(step_index, int) or step_index <= 0:
                        self.logger.warning(
                            f"Handler returned key_step with invalid index: {update}"
                        )
                        continue

                    if step_index > self.total_key_steps:
                        self.logger.warning(
                            f"Handler returned key_step index {
                                step_index
                            } exceeds total steps {self.total_key_steps}"
                        )
                        # Decide whether to skip or log anyway; here we log but warn

                    # Deduplication handled by KeyStepMetric; BaseEvaluator only logs
                    self.logger.info(
                        f"Handler reported key step completion: Index={
                            step_index
                        }, Name from Handler='{name_from_handler}'"
                    )

                    # Record KEY_STEP_COMPLETED event, including handler-provided name (if any)
                    event_data = {
                        "timestamp": current_time,
                        "step_index": step_index,
                    }
                    if name_from_handler is not None:
                        event_data["step_name"] = name_from_handler
                    self.record_event(AgentEvent.KEY_STEP_COMPLETED, event_data)

                case "app_event":  # Non-key app events for tracking
                    event_name = update.get("name", "unknown_app_event")
                    event_payload = update.get("payload", {})
                    self.logger.debug(
                        f"Handler reported app event: {event_name}, Data: {event_payload}"
                    )
                    # Record APP_SPECIFIC_EVENT
                    self.record_event(
                        AgentEvent.APP_SPECIFIC_EVENT,
                        {
                            "timestamp": current_time,
                            "name": event_name,
                            "payload": event_payload,
                        },
                    )

                case (
                    "continue" | None
                ):  # Handler explicitly indicates continue or no update
                    pass

                case _:
                    self.logger.warning(
                        f"Handler returned unrecognized status: '{status}' in {update}"
                    )

    def register_completion_callback(
        self, callback: Callable[[CallbackEventData, "BaseEvaluator"], None]
    ) -> None:
        """
        Register a callback function for task completion.

        Args:
            callback: Function that receives CallbackEventData and evaluator instance.
        """
        self.completion_callbacks.append(callback)
        self.logger.info("Registered a new completion callback")

    def _trigger_completion_callbacks(self, event_data: CallbackEventData) -> None:
        """
        Trigger all registered completion callbacks.

        Args:
            event_data: Callback event data containing event type and message.
        """
        self.logger.info(
            f"Triggering callback: {event_data.event_type} - {event_data.message}"
        )
        # Set final flag if this is a final state callback
        if event_data.event_type in ["task_completed", "task_error"]:
            self._final_callback_triggered = True

        for callback in self.completion_callbacks:
            try:
                callback(event_data, self)
            except Exception as e:
                self.logger.error(f"Error executing callback: {str(e)}")

    def start(self) -> bool:
        """
        Start the evaluator.

        Returns:
            bool: True if started successfully, False otherwise.
        """
        if self.is_running:
            self.logger.warning("Evaluator is already running")
            return False

        if not self.hook_manager.app_started:
            # Restore user data
            try:
                data_restore_config = self.config.get("context_data", [])
                for config in data_restore_config:
                    from_relative_path = config.get("from")
                    from_path = os.path.join(self.canary_root, from_relative_path)
                    to_path = config.get("to")
                    restore_context_data(from_path, to_path)
                    
                    # Optionally clear VSCode user storage after restore
                    # Only execute if explicitly enabled and path looks like VSCode user_data_dir
                    if (
                        self.config.get('clear_vscode_storage_on_restore', False)
                        and 'vscode' in to_path.lower()
                        and 'user_data_dir' in to_path.lower()
                    ):
                        from evaluator.utils.vscode_userdata import clear_vscode_user_storage
                        clear_vscode_user_storage(to_path, logger=self.logger)

            except Exception as e:
                self.logger.error(f"Failed to restore user data: {str(e)}")
                return False
            self.logger.info("User data successfully restored")
            self.start_app()

        try:
            self.is_running = True

            # 1. Prepare session data (including configuration snapshot)
            session_data = {
                "app_path": self.hook_manager.app_path,
                "app_process_pid": self.hook_manager.app_process.pid
                if self.hook_manager.app_process
                else None,
            }
            # 2. Start ResultCollector session and register metrics (must happen before hook load)
            self.result_collector.start_session(self.task_id, session_data, self.config)

            # Record TASK_START event immediately
            self.record_event(
                AgentEvent.TASK_START,
                {
                    "timestamp": self.result_collector.results[self.task_id][
                        "metadata"
                    ]["session_start_unix"]
                },
            )

            # 3. Load hook scripts, which may start sending events immediately
            load_success = self.hook_manager.load_scripts(self._on_message)
            if not load_success:
                self.logger.warning(
                    "Hook manager reported failure while loading scripts; continuing without injected hooks."
                )
            else:
                self.logger.debug("Hook manager loaded scripts successfully.")

            self.logger.info("Evaluator started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Evaluator failed to start: {str(e)}")
            return False

    def stop(self) -> None:
        """
        Stop the evaluation.
        """
        if not self.is_running:
            self.logger.warning("Evaluator is not running")
            return

        try:
            # First, set is_running to False to prevent loops
            self.is_running = False
            # Unload hook scripts
            self.hook_manager.unload_scripts()

            # If the final callback (success/failure) has not been triggered, record TASK_END event
            if not self._final_callback_triggered:
                stop_message = "Evaluator stopped externally or timed out before handler completion"
                self.logger.warning(stop_message)
                self.record_event(
                    AgentEvent.TASK_END, {"status": "stopped", "reason": stop_message}
                )
                # Optionally trigger an "evaluator_stopped" callback for external logic
                # self._trigger_completion_callbacks(CallbackEventData("evaluator_stopped", stop_message))

            # End the session and compute final metrics
            self.result_collector.end_session(self.task_id)

            # Save results (now including computed metrics)
            self.save_results()  # <- Moved here to ensure saving happens once at the end
        except Exception as e:
            self.logger.error(f"Failed to stop evaluator: {str(e)}")

    def start_app(self) -> bool:
        """
        Start the application if an application path is provided.

        Returns:
            bool: True if started successfully, False otherwise
        """
        return self.hook_manager.start_app()

    def stop_app(self) -> None:
        """
        Stop the application process.
        """
        return self.hook_manager.stop_app()

    def save_results(self) -> str:
        """
        Save evaluation results.

        Returns:
            str: Path to the results file
        """
        results_path = self.result_collector.save_results(self.task_id)
        self.logger.info(f"Evaluation results saved: {results_path}")
        return results_path

    def generate_report(self) -> str:
        """
        Generate the evaluation report.

        Returns:
            str: Path to the report file
        """
        # Base class provides a basic report; subclasses can override for more detailed reports
        report_path = os.path.join(self.session_dir, f"{self.task_id}_report.md")

        # Get final results from ResultCollector
        results = self.result_collector.get_results(self.task_id)
        metadata = results.get("metadata", {})
        computed_metrics = results.get("computed_metrics", {})
        raw_events = results.get("raw_events", [])

        # Use time information from metadata
        start_time_iso = metadata.get("session_start_iso", "Unknown")
        end_time_iso = metadata.get("session_end_iso", "Unknown")
        duration_val = metadata.get("session_duration_seconds")
        duration_str = (
            f"{duration_val:.2f}"
            if isinstance(duration_val, (int, float))
            else "Unknown"
        )

        # Basic report template
        report_content = f"""# {self.task_id} Evaluation Report

## Basic Information
- Task ID: {self.task_id}
- Session ID: {self.session_id}
- Start Time: {start_time_iso}
- End Time: {end_time_iso}
- Total Duration: {duration_str} seconds

## Evaluation Metrics
"""
        # Add computed metrics
        if computed_metrics:
            for name, value in computed_metrics.items():
                # Format complex values as JSON for readability
                value_str = (
                    json.dumps(value, ensure_ascii=False, indent=2)
                    if isinstance(value, (dict, list))
                    else value
                )
                report_content += f"- {name}: {value_str}\n"
        else:
            report_content += "- No metrics computed.\n"

        # Add event logs
        report_content += "\n## Event Logs\n"
        if raw_events:
            for event in raw_events:
                ts = event.get("timestamp", 0)
                event_time_str = (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                    if ts
                    else "N/A"
                )
                event_type_str = event.get("event_type", "UNKNOWN_EVENT")
                event_data_str = json.dumps(
                    {
                        k: v
                        for k, v in event.items()
                        if k not in ["timestamp", "event_type"]
                    },
                    ensure_ascii=False,
                )
                report_content += (
                    f"- [{event_time_str}] {event_type_str}: {event_data_str}\n"
                )
        else:
            report_content += "- No raw events recorded.\n"

        # Write the report file
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            self.logger.info(f"Evaluation report generated: {report_path}")
        except Exception as e:
            self.logger.error(
                f"Failed to generate evaluation report: {e}", exc_info=True
            )
            return ""  # Return empty string to indicate failure

        return report_path
