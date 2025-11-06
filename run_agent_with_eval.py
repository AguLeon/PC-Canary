#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to integrate the Agent system with the Evaluator
"""

from env.controller.code_execution_controller import CodeExecutionController
from evaluator.core.base_evaluator import AgentEvent
from evaluator.core.base_evaluator import BaseEvaluator, CallbackEventData
from agent.models.claude_model import ClaudeModel
from agent.models.openai_model import OpenAIModel
from agent.base_agent import BaseAgent
import os
import sys
import time
import argparse
import signal
# from PIL import Image

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

# Import Agent-related modules (adjust according to actual project structure)

# Import evaluator

# Import environment controller

start_time = None
# Global flag similar to run_evaluator.py
evaluation_finished = False


def handle_evaluator_event(event_data: CallbackEventData, evaluator: BaseEvaluator = None):
    """Callback function to handle evaluator events"""
    print(f"\nReceived evaluator event: {event_data.event_type} - {event_data.message}")

    global evaluation_finished

    if event_data.event_type == "task_completed":
        print(f"Evaluator reported successful task completion: {event_data.message}")
        evaluation_finished = True  # Signal loop termination

    elif event_data.event_type == "task_error":
        print(f"Evaluator reported task error: {event_data.message}")
        evaluation_finished = True  # Signal loop termination

    elif event_data.event_type == "evaluator_stopped":
        print(f"Evaluator stopped: {event_data.message}")
        # evaluation_finished = True  # Optionally stop loop on external stop


def _generate_report(evaluator, agent_success):
    """Generate execution report"""
    print("\n" + "=" * 60)
    print("Agent System & Evaluator Execution Report")
    print("=" * 60)
    print(f"Execution Time: {time.time() - start_time:.2f} seconds")

    # Get evaluation results
    final_results = evaluator.result_collector.get_results(evaluator.task_id)
    computed_metrics = final_results.get('computed_metrics', {})
    final_status = computed_metrics.get('task_completion_status', {})
    eval_success = final_status.get('status') == 'success'

    # Compare results
    print("\nResult Comparison:")
    print(
        f"- Agent system result: {'Success' if agent_success else 'Failure'}")
    print(f"- Evaluator result: {'Success' if eval_success else 'Failure'} (Status: {final_status.get('status', 'Unknown')})")

    # Check consistency
    is_consistent = (agent_success == eval_success)
    print(
        f"- Result consistency: {'Consistent' if is_consistent else 'Inconsistent'}")

    # Print evaluator detailed results
    print("\nEvaluator Metric Details:")
    if computed_metrics:
        import json  # Make sure json is imported
        for key, value in computed_metrics.items():
            value_str = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(
                value, (dict, list)) else value
            print(f"- {key}: {value_str}")
    else:
        print("- No metrics were computed.")

    # Fetch result file path from metadata if available
    result_file = final_results.get('metadata', {}).get('result_file_path')
    if result_file:
        print(f"\nResult file: {result_file}")
    else:
        # save_results is called in finally block
        print("\nResult file path not found in metadata.")

    print("\n" + "=" * 60)
    print("Execution completed")
    print("=" * 60 + "\n")

    return agent_success, eval_success


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Run the Agent system with integrated Evaluator")
    parser.add_argument("--model", choices=["openai", "gemini", "qwen", "claude"], default="claude",
                        help="Model type to use (default: openai)")
    parser.add_argument("--api_key", type=str, default=None,
                        help="API key (if not provided, will be read from environment variable)")
    parser.add_argument("--app_path", type=str, default="apps/tdesktop/out/Debug/Telegram",
                        help="Path to Telegram app (default: apps/tdesktop/out/Debug/Telegram)")
    parser.add_argument("--max_steps", type=int, default=10,
                        help="Maximum number of execution steps (default: 10)")
    parser.add_argument("--log_dir", type=str, default="logs",
                        help="Directory for logs (default: logs)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout in seconds (default: 300)")

    args = parser.parse_args()

    # Check API key
    api_key = args.api_key
    if args.model == 'openai':
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
        model = OpenAIModel(
            api_key=api_key,
            model_name="gpt-4o-mini",
            temperature=0.2,
            max_tokens=2048
        )
    elif args.model == 'qwen':
        if api_key is None:
            api_key = os.environ.get('DASHSCOPE_API_KEY')
        model = OpenAIModel(
            api_key=api_key,
            model_name="qwen-vl-max",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.2,
            max_tokens=2048
        )
    elif args.model == 'claude':
        if api_key is None:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError(
                "Claude model requires an API Key (via --api_key or ANTHROPIC_API_KEY environment variable)")
        model = ClaudeModel(
            api_key=api_key,
            model_name="claude-3-7-sonnet-latest",
            temperature=0.2,
            max_tokens=2048,
        )
    else:
        raise ValueError(f"Unsupported model type: {args.model}")

    # Check application path
    if not os.path.exists(args.app_path):
        print(f"Warning: Telegram application path not found: {args.app_path}")
        if input("Continue execution anyway? (y/n): ").lower() != 'y':
            return 1

    # Create environment controller
    controller = CodeExecutionController()

    # Create Agent
    agent = BaseAgent(model, observation_type="screenshot",
                      action_space="pyautogui-muti-action")

    # Create Evaluator
    task = {
        "category": "telegram",
        "id": "task01_search",
    }
    evaluator = BaseEvaluator(task, args.log_dir, args.app_path)

    # Set signal handler
    def _signal_handler(sig, frame):
        """Handle termination signals"""
        print("\n\nExecution interrupted by user...")
        if evaluator and evaluator.is_running:
            print("Stopping evaluator...")
            evaluator.stop()
            evaluator.stop_app()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    os.makedirs(args.log_dir, exist_ok=True)

    print("\n" + "=" * 60)
    print(
        f"Running Agent system with integrated Evaluator - using {args.model} model")
    print("=" * 60)
    print("Task: Search for 'news' in Telegram")
    print(f"Max steps: {args.max_steps}")
    print(f"Application path: {args.app_path}")
    print("=" * 60 + "\n")

    # Register callback
    evaluator.register_completion_callback(handle_evaluator_event)

    print("[*] Starting evaluator...")
    success = evaluator.start()
    if not success:
        print("Failed to start evaluator")
        return 1

    global start_time
    # Record start time
    start_time = time.time()

    # Define Telegram search task instruction
    instructions = """
    Task: Perform a search operation in the Telegram application

    Steps:
    1. Launch the Telegram application (if already open, ensure it’s in the foreground)
    2. Click on the search button (usually located at the top)
    3. Type "news" in the search box
    4. Wait for the search results to appear
    """

    # Run Agent system
    agent_success = False
    try:
        print("\n[*] 开始执行Agent系统...")

        # 执行步骤
        step_index = 0

        while step_index < args.max_steps and not evaluation_finished:
            print(f"\n执行步骤 {step_index+1}/{args.max_steps}")
            current_time = time.time()  # For event timestamps

            # 检查是否超时
            if current_time - start_time > args.timeout:
                print(f"\n执行超时 ({args.timeout}秒)")
                # Don't call evaluator.stop() here, let finally block handle it
                break

            # 获取观察
            print("获取屏幕截图...")
            observation = controller.get_screenshot()
            if not observation:
                print("无法获取屏幕截图，跳过此步骤")
                time.sleep(1)  # Avoid rapid looping on error
                continue

            # --- LLM 调用事件 --- #
            print("Agent开始决策...")
            llm_start_time = time.time()
            evaluator.record_event(AgentEvent.LLM_QUERY_START, {
                'timestamp': llm_start_time,
                'model_name': agent.model.model_name  # Assuming model has model_name attribute
            })
            action_code = None
            thought = None
            usage_info = None  # Initialize usage_info before try block
            llm_error = None
            llm_success = False
            try:
                # action, args, usage_info = agent.act(instructions, observation, controller)
                # Unpack the three return values
                returned_action, returned_args, usage_info = agent.act(
                    instructions, observation, controller)
                llm_success = True  # LLM call itself succeeded if no exception
            except Exception as llm_e:
                llm_error = str(llm_e)
                print(f"Agent决策时发生错误: {llm_error}")
                # usage_info might still be None here if error happened before return

            llm_end_time = time.time()
            # Record LLM_QUERY_END using the returned usage_info
            evaluator.record_event(AgentEvent.LLM_QUERY_END, {
                'timestamp': llm_end_time,
                'status': 'success' if llm_success else 'error',
                'error': llm_error,
                'prompt_tokens': usage_info.get('prompt_tokens') if usage_info else None,
                'completion_tokens': usage_info.get('completion_tokens') if usage_info else None,
                'cost': None  # Cost calculation not implemented
            })

            # Check if LLM call failed or returned nothing actionable initially
            if not llm_success:
                print("LLM 调用失败，跳过此步骤。")
                time.sleep(1)
                continue
            if returned_action is None and returned_args and returned_args.get("error"):
                print(f"LLM 返回错误或无法解析: {returned_args.get('error')}")
                time.sleep(1)
                continue

            # --- Handle special instructions returned by Agent --- #
            if returned_action == "finish":
                print("Agent 报告任务完成 (finish)。")
                agent_success = True
                reasoning = returned_args.get(
                    'reasoning', 'No reasoning provided') if returned_args else 'No reasoning provided'
                evaluator.record_event(AgentEvent.AGENT_REPORTED_COMPLETION, {
                    'timestamp': time.time(),
                    'reasoning': reasoning
                })
                break  # Exit the main loop

            elif returned_action == "wait":
                print("Agent 请求等待，跳过执行。")
                time.sleep(1)  # Implement actual wait or just continue
                continue  # Skip code execution for this step

            elif returned_action == "fail":
                print("Agent 报告任务失败 (fail)。")
                agent_success = False
                reasoning = returned_args.get(
                    'reasoning', 'No reasoning provided') if returned_args else 'No reasoning provided'
                # Optionally record an event here if needed, though handler might record TASK_END
                # evaluator.record_event(...)
                break  # Exit the main loop

            # --- If it's code, proceed with execution --- #
            action_code = returned_action  # Now we know it should be code
            if not isinstance(action_code, str):
                print(f"错误: agent.act 返回的动作不是预期的代码字符串或特殊指令: {action_code}")
                time.sleep(1)
                continue

            # --- Action (Tool) 执行事件 --- #
            print(f"准备执行动作代码: {action_code[:100]}...")  # Log snippet
            tool_start_time = time.time()
            tool_name = "code_execution"
            evaluator.record_event(AgentEvent.TOOL_CALL_START, {
                'timestamp': tool_start_time,
                'tool_name': tool_name,
                'args': {'code': action_code}  # Store code as args
            })
            execution_result = None
            tool_error = None
            tool_success = False
            try:
                execution_result = agent._execute_action(
                    action_code, controller)
                tool_success = True  # Assume success if no exception
                print(f"动作执行结果: {execution_result}")
            except Exception as tool_e:
                tool_error = str(tool_e)
                print(f"动作执行时发生错误: {tool_error}")

            tool_end_time = time.time()
            evaluator.record_event(AgentEvent.TOOL_CALL_END, {
                'timestamp': tool_end_time,
                'tool_name': tool_name,
                'success': tool_success,
                'result': execution_result if tool_success else None,
                'error': tool_error
            })

            # 检查环境状态 (由 Evaluator 触发的回调会设置 evaluation_finished)
            # if controller.task_completed: # Rely on evaluator callback now
            #     print("Agent报告任务已完成！")
            #     agent_success = True
            #     break
            # elif controller.task_failed: # Rely on evaluator callback now
            #     print(f"Agent报告任务失败！原因: {controller.failure_reason}")
            #     break

            # Agent 自身是否认为完成？ (如果 agent.act 返回此信息)
            # agent_thinks_complete = thought.get('final_answer') is not None # Example check
            # if agent_thinks_complete:
            #    evaluator.record_event(AgentEvent.AGENT_REPORTED_COMPLETION, { 'timestamp': time.time(), 'reasoning': thought })

            # 继续执行下一步
            step_index += 1
            # 短暂等待以允许回调处理
            time.sleep(0.5)

        # 打印Agent执行结果
        print(f"\n[*] Agent执行{'成功' if agent_success else '失败'}")

        # 等待评估器完成处理
        print("[*] 等待评估器完成处理...")
        time.sleep(3)

    except KeyboardInterrupt:
        print("\n[!] 用户中断执行")
    except Exception as e:
        print(f"\n[!] 执行错误: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止评估器
        if evaluator.is_running:
            print("\n[*] 停止评估器...")
            evaluator.stop()

        # 停止应用
        if hasattr(evaluator, 'stop_app'):
            evaluator.stop_app()

    agent_success, eval_success = _generate_report(evaluator, agent_success)
    overall_success = agent_success and eval_success
    print(f"\n总体执行结果: {'成功' if overall_success else '失败'}")
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
