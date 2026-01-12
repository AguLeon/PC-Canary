#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal Evaluator Runner Script
Used to run any evaluation task defined under tests/tasks directory.

Usage:
python run_evaluator.py --app telegram --task task01_search --app-path /path/to/app [--custom-params '{"query":"news"}']
"""

from evaluator.core.base_evaluator import BaseEvaluator, CallbackEventData
import os
import sys
import time
import json
import argparse
import signal
from typing import Dict, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)


# Global flag to signal loop termination from callback
evaluation_finished = False


# Signal handler
def signal_handler(sig, frame, evaluator=None):
    """
    Handle CTRL+C signal

    Args:
        sig: Signal type
        frame: Stack frame
        evaluator: Evaluator instance
    """
    print("\n\nEvaluation interrupted by user...")

    if evaluator and evaluator.is_running:
        print("Stopping evaluator...")
        evaluator.set_stop_context(
            reason="Execution interrupted by user (SIGINT)", status="stopped"
        )
        evaluator.stop()
        evaluator.stop_app()
    sys.exit(0)


def handle_evaluator_event(event_data: CallbackEventData, evaluator: BaseEvaluator):
    """
    Callback function to handle evaluator events

    Args:
        event_data: Event data
        evaluator: Evaluator instance
    """
    print(f"\nReceived evaluator event: {event_data.event_type} - {event_data.message}")

    global evaluation_finished

    if event_data.event_type == "task_completed":
        print("Task completed successfully")
        evaluation_finished = True  # Signal the main loop to stop

    elif event_data.event_type == "task_error":
        print("Task encountered an error")
        evaluation_finished = True

    elif event_data.event_type == "evaluator_stopped":
        print("Evaluator stopped")


def print_app_instructions(app: str, task: str, instruction: str):
    """
    Print user instructions for the given app and task

    Args:
        app: Application name
        task: Task ID
        instruction: Task instruction
    """
    print("\n" + "=" * 60)
    print(f"{app.capitalize()} evaluator is running...")
    print(f"Task: {task}")
    print(f"Task instruction: {instruction}")
    print("\nPlease follow these steps:")
    print("1. The app will automatically start (if a path is provided)")
    print("2. Operate the app according to the above task instruction")
    print("3. The evaluator will automatically monitor your actions")
    print("4. You will be notified when the task completes")
    print("5. You can press CTRL+C anytime to stop the evaluation")
    print("=" * 60 + "\n")


def load_config(app: str, task: str) -> Optional[Dict]:
    """
    Load configuration file for the specified app and task

    Args:
        app: Application name
        task: Task ID

    Returns:
        Dict: Configuration file contents, or None if loading fails
    """
    config_path = os.path.join(
        PROJECT_ROOT, "tests", "tasks", app, task, "config.json")
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Failed to load configuration file: {str(e)}")
        return None


def parse_custom_params(params_str: str) -> Dict:
    """
    Parse custom parameters JSON string into a dictionary

    Args:
        params_str: JSON-format string of parameters

    Returns:
        Dict: Parsed parameters dictionary
    """
    if not params_str:
        return {}

    try:
        return json.loads(params_str)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse custom parameters: {str(e)}")
        print("Using empty parameter dictionary")
        return {}


def list_available_tasks():
    """
    List all available apps and tasks
    """
    tasks_dir = os.path.join(PROJECT_ROOT, "tests", "tasks")
    if not os.path.exists(tasks_dir):
        print("Error: Tasks directory does not exist")
        return

    print("\nAvailable apps and tasks:")
    print("=" * 60)

    for app in os.listdir(tasks_dir):
        app_dir = os.path.join(tasks_dir, app)
        if not os.path.isdir(app_dir):
            continue

        print(f"App: {app}")
        for task in os.listdir(app_dir):
            task_dir = os.path.join(app_dir, task)
            if not os.path.isdir(task_dir):
                continue

            config_path = os.path.join(task_dir, "config.json")
            task_desc = ""
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        task_desc = config.get("description", "")
                except:
                    pass

            print(f"  - Task: {task} {task_desc}")

        print("-" * 60)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Universal Evaluator Runner Script")
    parser.add_argument("--app", type=str,
                        help="Name of the application to evaluate")
    parser.add_argument("--task", type=str, help="ID of the task to run")
    parser.add_argument("--app-path", type=str,
                        help="Path to the application executable")
    parser.add_argument(
        "--log-dir", type=str, default="logs", help="Log directory (default: logs)"
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="Timeout in seconds (default: 300)"
    )
    parser.add_argument("--custom-params", type=str,
                        help="Custom parameters in JSON format")
    parser.add_argument("--list", action="store_true",
                        help="List all available apps and tasks")

    args = parser.parse_args()

    # If --list flag is used, list available tasks and exit
    if args.list:
        list_available_tasks()
        return 0

    # Check required parameters
    if not args.app or not args.task:
        print("Error: You must specify both --app and --task")
        parser.print_help()
        return 1

    # Check if task directory exists
    task_path = os.path.join(PROJECT_ROOT, "tests",
                             "tasks", args.app, args.task)
    if not os.path.exists(task_path):
        print(f"Error: Task directory not found: {task_path}")
        return 1

    # Load task configuration
    config = load_config(args.app, args.task)
    if not config:
        return 1
    # Handle application path
    app_path = args.app_path
    if not app_path and "application_info" in config:
        app_path = config["application_info"].get("executable_path")

    if app_path and not os.path.exists(app_path):
        print(f"Warning: Application executable not found: {app_path}")
        user_choice = input(
            "Continue evaluation anyway? (y/n): ").strip().lower()
        if user_choice != "y":
            return 0
        app_path = None  # If file doesn’t exist but user chooses to continue, set to None

    # Parse custom parameters
    custom_params = parse_custom_params(args.custom_params)

    # Create log directory
    log_dir = args.log_dir
    os.makedirs(log_dir, exist_ok=True)

    # Task information
    task = {
        "category": args.app,
        "id": args.task,
    }

    print("Initializing evaluator...")
    print(f"Application: {args.app}")
    print(f"Task: {args.task}")
    if app_path:
        print(f"Application path: {app_path}")
    if custom_params:
        print(f"Custom parameters: {json.dumps(
            custom_params, ensure_ascii=False)}")

    evaluator = None

    try:
        # Set signal handler
        def handler(sig, frame):
            return signal_handler(sig, frame, evaluator)

        signal.signal(signal.SIGINT, handler)

        # Create evaluator
        evaluator = BaseEvaluator(
            task, log_dir, app_path, custom_params=custom_params)

        # Register callback function
        evaluator.register_completion_callback(handle_evaluator_event)

        # Start evaluator
        success = evaluator.start()
        if not success:
            print("Failed to start evaluator")
            return 1

        # Print operation guide
        print_app_instructions(args.app, args.task, evaluator.instruction)

        # Set timeout
        timeout_seconds = args.timeout
        start_time = time.time()

        # Main loop — waits for task completion or timeout (callback sets evaluation_finished)
        while not evaluation_finished:
            # Check for timeout
            if time.time() - start_time > timeout_seconds:
                print(f"\nEvaluation timed out ({timeout_seconds} seconds)...")
                evaluator.set_stop_context(
                    reason=f"Evaluation timed out after {timeout_seconds} seconds",
                    status="timeout",
                )
                evaluator.stop()
                time.sleep(10)
                break

        # Stop evaluator if still running
        if evaluator.is_running:
            print("Stopping evaluator...")
            evaluator.stop()
            time.sleep(1)  # Allow time for shutdown

        # Retrieve and print final computed metrics (optional, since results are saved to file)
        final_results = evaluator.result_collector.get_results(
            evaluator.task_id)
        computed_metrics = final_results.get('computed_metrics', {})
        final_status = computed_metrics.get('task_completion_status', {})

        print("\nEvaluation task finished!")
        print("Final computed metrics:")
        if computed_metrics:
            for key, value in computed_metrics.items():
                value_str = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(
                    value, (dict, list)) else value
                print(f"  {key}: {value_str}")
        else:
            print("  No metrics could be computed.")

        print(f"\nFinal task status: {final_status.get('status', 'Unknown')}")
        if final_status.get('reason'):
            print(f"Reason: {final_status.get('reason')}")

        # Locate and display result file
        result_file = evaluator.save_results()
        if result_file:
            print(f"\nResult file saved at: {result_file}")

        # Stop the application
        evaluator.stop_app()

    except Exception as e:
        import traceback

        print(f"Error occurred during evaluation: {e}")
        print(traceback.format_exc())
        if evaluator and evaluator.is_running:
            evaluator.stop()
            evaluator.stop_app()
        return 1

    print("Evaluation script exited normally")
    return 0


if __name__ == "__main__":
    sys.exit(main())
