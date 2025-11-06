#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Search Task Test Program - Using Code Execution Environment Controller
"""

import os
import sys
import time
# from PIL import Image, ImageGrab
import argparse

# Import Agent-related modules
from agent.base_agent import BaseAgent
from agent.models.openai_model import OpenAIModel
from agent.models.gemini_model import GeminiModel
from agent.models.claude_model import ClaudeModel

# Import controller
from env.controller.code_execution_controller import CodeExecutionController

# Import new logging system
from utils.logger import AgentLogger


def create_model(model_type, api_key):
    """
    Create model instance

    Args:
        model_type: Type of model ('openai' or 'gemini')
        api_key: API key

    Returns:
        Model instance
    """
    if model_type.lower() == 'openai':
        return OpenAIModel(
            api_key=api_key,
            model_name="gpt-4o-mini",
            temperature=0.2,
            max_tokens=2048
        )
    elif model_type.lower() == 'gemini':
        return GeminiModel(
            api_key=api_key,
            model_name="gemini-1.5-pro",
            temperature=0.2,
            max_output_tokens=2048
        )
    elif model_type.lower() == 'qwen':
        return OpenAIModel(
            api_key=api_key,
            model_name="qwen-vl-max",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.2,
            max_tokens=2048
        )
    elif model_type.lower() == 'claude':
        if not api_key:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError(
                "Using the Claude model requires an API Key (via --api_key or ANTHROPIC_API_KEY environment variable)")
        return ClaudeModel(
            api_key=api_key,
            model_name="claude-3-7-sonnet-latest",
            temperature=0.2,
            max_tokens=2048,
        )
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


def test_agent_telegram_search(model_type='openai', api_key=None, max_steps=10):
    """
    Test Agent executing task

    Args:
        model_type: Model type ('openai' or 'gemini')
        api_key: API key (if None, it will attempt to fetch from environment variables)
        max_steps: Maximum number of execution steps

    Returns:
        bool: Whether the task was successfully completed
    """
    # Check API key
    if api_key is None:
        if model_type.lower() == 'openai':
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "OpenAI API key not provided. Please set OPENAI_API_KEY environment variable or pass api_key argument")
        elif model_type.lower() == 'gemini':
            api_key = os.environ.get('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError(
                    "Google API key not provided. Please set GOOGLE_API_KEY environment variable or pass api_key argument")
        elif model_type.lower() == 'qwen':
            api_key = os.environ.get('DASHSCOPE_API_KEY')
            if not api_key:
                raise ValueError(
                    "Dashscope API key not provided. Please set DASHSCOPE_API_KEY environment variable or pass api_key argument")

    # Create model
    model = create_model(model_type, api_key)

    # Create code execution environment controller
    controller = CodeExecutionController()

    # Create Agent
    agent = BaseAgent(model, observation_type="screenshot",
                      action_space="pyautogui-muti-action")

    # Initialize logging system
    logger = AgentLogger(base_log_dir="logs")
    print(f"Logs will be saved to: {logger.session_dir}")

    # Define Telegram search task instructions
    instructions = """
    Task: Perform a search operation in the Telegram application

    Steps:
    1. Launch the Telegram app (if already open, ensure it's in the foreground)
    2. Click the search button (usually located at the top of the app)
    3. Type "news" in the search box
    4. Wait for the search results to appear

    Notes:
    - You can use the pyautogui library to control the mouse and keyboard
    - You can use the WAIT command to wait for the interface response (e.g., WAIT)
    - When the task is completed, use the DONE command
    - If the task cannot be completed, use the FAIL command
    - You have access to the following environment variables and libraries: pyautogui, time, os, sys, re, json, PIL, ImageGrab
    - You can access the controller instance via the controller variable
    """

    # Log task start
    logger.start_step(instructions)

    # Execute steps
    step_index = 0
    start_time = time.time()

    print(f"\nStarting Telegram search task, using {model_type} model\n")
    print(f"Task instructions:\n{instructions}\n")

    # Execute Agent loop
    while step_index < max_steps and not controller.task_completed and not controller.task_failed:
        print(f"\nExecuting step {step_index+1}/{max_steps}")

        # Start new step logging
        if step_index > 0:
            logger.start_step(f"Executing step {step_index+1}")

        # Get observation
        print("Getting screenshot...")
        observation = controller.get_screenshot()

        # Save screenshot to logging system
        screenshot_path = logger.log_screenshot(observation)
        print(f"Screenshot saved: {screenshot_path}")

        # Perform Agent decision
        print("Agent is deciding...")
        action, args, usage_info = agent.act(
            instructions, observation, controller)

        # Log action and potential arguments (like reasoning or errors)
        logger.log_action(action, args)

        # --- Handle different action types --- #
        if action == "finish":
            print("Agent reports task completed (finish).")
            print(f"Reasoning: {args.get('reasoning', 'N/A')}" if args else "")
            controller.task_completed = True  # Mark controller state as well
            break  # Exit loop

        elif action == "wait":
            print("Agent requests wait.")
            # Optionally add a sleep here based on args if provided
            time.sleep(1)  # Simple wait
            continue  # Go to next step without execution

        elif action == "fail":
            print("Agent reports task failed (fail).")
            print(f"Reasoning: {args.get('reasoning', 'N/A')}" if args else "")
            controller.task_failed = True
            controller.failure_reason = args.get(
                'reasoning', 'Agent reported FAIL') if args else 'Agent reported FAIL'
            break  # Exit loop

        elif action is None:
            print(f"Agent decision or parsing error: {
                  args.get('error', 'Unknown error')}")
            controller.task_failed = True
            controller.failure_reason = args.get(
                'error', 'Agent act returned None') if args else 'Agent act returned None'
            break  # Exit loop

        # --- If action is code, execute it --- #
        elif isinstance(action, str):
            action_code = action  # It's Python code
            # Print Agent thinking and actions (Thought is no longer returned directly)
            print(f"\nAgent action (code):")
            print("-" * 50)
            print(action_code[:500] +
                  ("..." if len(action_code) > 500 else ""))
            print("-" * 50)

            # Execute code and get execution result
            execution_result = agent._execute_action(action_code, controller)

            # Log execution result to the logging system
            logger.log_execution_result(execution_result)
        else:
            print(f"Unknown Agent action type: {action}")
            controller.task_failed = True
            controller.failure_reason = f"Unknown action type: {action}"
            break

        # Check if timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > 300:  # 5 minutes timeout
            print("Test timed out, terminating execution")
            logger.end_session("timeout")
            break

        # User can manually interrupt
        print("\nPress 'q' to quit, or press any key to continue...")
        if sys.stdin.isatty():  # Check if in interactive terminal
            try:
                import termios
                import tty
                import select
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    if select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1)
                        if key == 'q':
                            print("User manually terminated the test")
                            logger.end_session("user_terminated")
                            break
                finally:
                    termios.tcsetattr(
                        sys.stdin, termios.TCSADRAIN, old_settings)
            except (ImportError, termios.error):
                pass

    # Generate simple report
    print("\n" + "="*50)
    print("Agent Test Execution Report")
    print("="*50)
    print(f"Executed steps: {step_index+1}/{max_steps}")
    print(f"Execution time: {time.time() - start_time:.2f} seconds")
    print(f"Execution status: {
          'Success' if controller.task_completed else 'Failure' if controller.task_failed else 'Not completed'}")
    if controller.task_failed:
        print(f"Failure reason: {controller.failure_reason}")

    print(f"\nComplete log has been saved to: {logger.session_dir}")
    print(f"Report file: {os.path.join(
        logger.session_dir, 'session_report.md')}")

    return controller.task_completed


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Test Agent performing Telegram search task")
    parser.add_argument("--model", choices=["openai", "gemini", "qwen", "claude"], default="claude",
                        help="Model type to use (default: claude)")
    parser.add_argument("--api_key", type=str,
                        help="API key (if not provided, it will be fetched from environment variables)")
    parser.add_argument("--max_steps", type=int, default=10,
                        help="Maximum number of steps to execute (default: 10)")

    args = parser.parse_args()

    try:
        # Test the agent
        success = test_agent_telegram_search(
            model_type=args.model,
            api_key=args.api_key,
            max_steps=args.max_steps
        )

        print(f"\nTest {'succeeded' if success else 'failed'}")

    except KeyboardInterrupt:
        print("\nUser interrupted, exiting the program")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
