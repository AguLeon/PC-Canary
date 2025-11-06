#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advanced Logging System - Records code execution, saves screenshots,
and marks action locations.
"""

import os
import re
import json
import time
import uuid
import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class AgentLogger:
    """
    Agent Execution Log Management System
    Supports recording code execution, saving screenshots,
    and marking points of action.
    """

    def __init__(self, base_log_dir="logs", session_id=None):
        """
        Initialize the logging system.

        Args:
            base_log_dir: Base directory for log storage.
            session_id: Session ID (auto-generated if not provided).
        """
        self.base_log_dir = base_log_dir
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = session_id or f"{self.timestamp}_{uuid.uuid4().hex[:8]}"

        # Create session directory structure
        self.session_dir = os.path.join(self.base_log_dir, self.session_id)
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        self.actions_dir = os.path.join(self.session_dir, "actions")
        self.metadata_dir = os.path.join(self.session_dir, "metadata")

        # Ensure directories exist
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.actions_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

        # Initialize session metadata
        self.session_log = {
            "session_id": self.session_id,
            "start_time": time.time(),
            "steps": [],
            "status": "running",
        }
        self._save_session_metadata()

        # Track current step index
        self.current_step = 0

        # Font settings (for marking screenshots)
        try:
            # Try loading a system font
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian/Ubuntu
                "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    self.font = ImageFont.truetype(font_path, 20)
                    break
            else:
                # Use default font if no system font found
                self.font = ImageFont.load_default()
        except Exception as e:
            print(f"Unable to load font, using default font: {e}")
            self.font = ImageFont.load_default()

    def _save_session_metadata(self):
        """Save session metadata."""
        with open(
            os.path.join(self.metadata_dir, "session.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(self.session_log, f, ensure_ascii=False, indent=2)

    def start_step(self, instruction=None):
        """
        Start a new step in the log.

        Args:
            instruction: Instruction for this step.

        Returns:
            The current step index.
        """
        self.current_step += 1

        # Create step entry
        step_data = {
            "step_id": self.current_step,
            "start_time": time.time(),
            "instruction": instruction,
            "screenshot": None,
            "action_code": None,
            "thought": None,
            "execution_result": None,
            "marked_screenshot": None,
        }

        self.session_log["steps"].append(step_data)
        self._save_session_metadata()

        return self.current_step

    def log_screenshot(self, screenshot, step_id=None):
        """
        Record a screenshot.

        Args:
            screenshot: A PIL.Image object or a path to an image.
            step_id: Step ID (if None, uses current step).

        Returns:
            Path to the saved screenshot.
        """
        step_id = step_id or self.current_step

        # Ensure screenshot is a PIL.Image object
        if isinstance(screenshot, str):
            screenshot = Image.open(screenshot)

        # Save the screenshot
        screenshot_filename = f"step_{step_id}_screenshot_{int(time.time())}.png"
        screenshot_path = os.path.join(self.screenshots_dir, screenshot_filename)
        screenshot.save(screenshot_path)

        # Update step data
        for step in self.session_log["steps"]:
            if step["step_id"] == step_id:
                step["screenshot"] = screenshot_path
                break

        self._save_session_metadata()
        return screenshot_path

    def log_action(self, action_code, thought=None, step_id=None):
        """
        Record executed code action.

        Args:
            action_code: The executed code.
            thought: The reasoning or thought process.
            step_id: Step ID (if None, uses current step).
        """
        step_id = step_id or self.current_step

        # Save code to a file
        action_filename = f"step_{step_id}_action_{int(time.time())}.py"
        action_path = os.path.join(self.actions_dir, action_filename)

        with open(action_path, "w", encoding="utf-8") as f:
            f.write(action_code)

        # Update step data
        for step in self.session_log["steps"]:
            if step["step_id"] == step_id:
                step["action_code"] = action_path
                step["thought"] = thought
                break

        self._save_session_metadata()
        return action_path

    def log_execution_result(self, result, step_id=None):
        """
        Record the result of code execution.

        Args:
            result: The execution result.
            step_id: Step ID (if None, uses current step).
        """
        step_id = step_id or self.current_step

        # Update step data
        for step in self.session_log["steps"]:
            if step["step_id"] == step_id:
                step["execution_result"] = result
                break

        self._save_session_metadata()

    def _extract_click_coordinates(self, code):
        """
        Extract click coordinates from the given code.

        Args:
            code: The executed code.

        Returns:
            List [(x1, y1, description1), (x2, y2, description2), ...]
        """
        clicks = []

        # Match pyautogui.click(x, y) pattern
        pattern1 = r"pyautogui\.click\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)"
        matches1 = re.finditer(pattern1, code)
        for match in matches1:
            x, y = int(match.group(1)), int(match.group(2))
            line_start = code[: match.start()].rfind("\n")
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            line_end = code.find("\n", match.start())
            if line_end == -1:
                line_end = len(code)
            line = code[line_start:line_end].strip()
            description = f"Click at ({x}, {y})"
            if "#" in line:
                comment = line.split("#", 1)[1].strip()
                description = f"{description} - {comment}"
            clicks.append((x, y, description))

        # Match pyautogui.moveTo(x, y); pyautogui.click() pattern
        pattern2 = (
            r"pyautogui\.moveTo\s*\(\s*(\d+)\s*,\s*(\d+)\s*\).*?pyautogui\.click\s*\("
        )
        matches2 = re.finditer(pattern2, code, re.DOTALL)
        for match in matches2:
            x, y = int(match.group(1)), int(match.group(2))
            line_start = code[: match.start()].rfind("\n")
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            line_end = code.find("\n", match.start())
            if line_end == -1:
                line_end = len(code)
            line = code[line_start:line_end].strip()
            description = f"MoveTo+Click at ({x}, {y})"
            if "#" in line:
                comment = line.split("#", 1)[1].strip()
                description = f"{description} - {comment}"
            clicks.append((x, y, description))

        return clicks

    def mark_screenshot_with_clicks(
        self, screenshot_path=None, action_code=None, step_id=None
    ):
        """
        Mark click positions on a screenshot.

        Args:
            screenshot_path: Path to the screenshot (if None, uses the current step’s screenshot)
            action_code: Executed code (if None, uses the current step’s code)
            step_id: Step ID (if None, uses the current step)

        Returns:
            Path to the marked screenshot
        """
        step_id = step_id or self.current_step

        # Find step data
        step_data = None
        for step in self.session_log["steps"]:
            if step["step_id"] == step_id:
                step_data = step
                break

        if not step_data:
            print(f"Error: Could not find data for step {step_id}")
            return None

        # If no screenshot path provided, use the one from step data
        if not screenshot_path:
            screenshot_path = step_data.get("screenshot")
            if not screenshot_path:
                print(f"Error: Step {step_id} has no recorded screenshot")
                return None

        # If no action code provided, use the one from step data
        if not action_code:
            action_code_path = step_data.get("action_code")
            if not action_code_path:
                print(f"Error: Step {step_id} has no recorded code")
                return None
            with open(action_code_path, "r", encoding="utf-8") as f:
                action_code = f.read()

        # Extract click coordinates
        clicks = self._extract_click_coordinates(action_code)
        if not clicks:
            print(f"Info: No click operations detected in code for step {step_id}")
            return screenshot_path

        # Open screenshot and mark click positions
        try:
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            for i, (x, y, description) in enumerate(clicks):
                # Draw a labeled crosshair
                color = (255, 0, 0)  # Red

                # Cross lines
                draw.line((x - 15, y, x + 15, y), fill=color, width=2)
                draw.line((x, y - 15, x, y + 15), fill=color, width=2)

                # Circle
                draw.ellipse((x - 20, y - 20, x + 20, y + 20), outline=color, width=2)

                # Label text position (avoid going out of image bounds)
                text_y = y + 25
                if text_y > img.height - 30:
                    text_y = y - 45

                # Label background and text
                text = f"{i + 1}: {description}"
                text_width, text_height = draw.textbbox((0, 0), text, font=self.font)[
                    2:4
                ]
                draw.rectangle(
                    (x - 10, text_y, x + text_width, text_y + text_height),
                    fill=(255, 255, 200),
                )
                draw.text((x - 5, text_y), text, font=self.font, fill=(0, 0, 0))

            # Save marked image
            marked_filename = f"step_{step_id}_marked_{int(time.time())}.png"
            marked_path = os.path.join(self.screenshots_dir, marked_filename)
            img.save(marked_path)

            # Update step data
            step_data["marked_screenshot"] = marked_path
            self._save_session_metadata()

            return marked_path

        except Exception as e:
            print(f"Error while marking screenshot: {e}")
            return screenshot_path

    def end_session(self, status="completed"):
        """
        End the session record.

        Args:
            status: Session status ('completed', 'failed', or a custom value)
        """
        self.session_log["end_time"] = time.time()
        self.session_log["status"] = status
        self.session_log["duration"] = (
            self.session_log["end_time"] - self.session_log["start_time"]
        )

        # Generate session report
        self._generate_session_report()

        # Save final session data
        self._save_session_metadata()

    def _generate_session_report(self):
        """Generate a session report"""
        report_path = os.path.join(self.session_dir, "session_report.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Agent Execution Session Report\n\n")
            f.write(f"**Session ID:** {self.session_id}\n\n")
            f.write(
                f"**Start Time:** {
                    datetime.datetime.fromtimestamp(
                        self.session_log['start_time']
                    ).strftime('%Y-%m-%d %H:%M:%S')
                }\n\n"
            )
            f.write(
                f"**End Time:** {
                    datetime.datetime.fromtimestamp(
                        self.session_log['end_time']
                    ).strftime('%Y-%m-%d %H:%M:%S')
                }\n\n"
            )
            f.write(f"**Duration:** {self.session_log['duration']:.2f} seconds\n\n")
            f.write(f"**Status:** {self.session_log['status']}\n\n")

            f.write(f"## Step Execution Records\n\n")

            for step in self.session_log["steps"]:
                f.write(f"### Step {step['step_id']}\n\n")

                f.write(
                    f"**Start Time:** {
                        datetime.datetime.fromtimestamp(step['start_time']).strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                    }\n\n"
                )

                if step.get("instruction"):
                    f.write(f"**Instruction:**\n```\n{step['instruction']}\n```\n\n")

                if step.get("thought"):
                    f.write(
                        f"**Thought Process:**\n```\n{step['thought'][:500]}{
                            '...' if len(step['thought']) > 500 else ''
                        }\n```\n\n"
                    )

                if step.get("action_code"):
                    rel_path = os.path.relpath(step["action_code"], self.session_dir)
                    f.write(f"**Executed Code:** [View Full Code]({rel_path})\n\n")

                if step.get("marked_screenshot"):
                    rel_path = os.path.relpath(
                        step["marked_screenshot"], self.session_dir
                    )
                    f.write(
                        f"**Marked Screenshot:**\n\n![Marked Screenshot]({rel_path})\n\n"
                    )
                elif step.get("screenshot"):
                    rel_path = os.path.relpath(step["screenshot"], self.session_dir)
                    f.write(f"**Screenshot:**\n\n![Screenshot]({rel_path})\n\n")

                if step.get("execution_result"):
                    if isinstance(step["execution_result"], dict):
                        f.write(
                            f"**Execution Result:**\n```json\n{
                                json.dumps(
                                    step['execution_result'],
                                    ensure_ascii=False,
                                    indent=2,
                                )
                            }\n```\n\n"
                        )
                    else:
                        f.write(
                            f"**Execution Result:**\n```\n{step['execution_result']}\n```\n\n"
                        )

                f.write("\n---\n\n")

        return report_path

    def get_session_info(self):
        """
        Get session information.

        Returns:
            A dictionary containing session information.
        """
        return {
            "session_id": self.session_id,
            "session_dir": self.session_dir,
            "steps_count": len(self.session_log["steps"]),
            "status": self.session_log["status"],
            "current_step": self.current_step,
        }


# Example usage
if __name__ == "__main__":
    # Create the logger
    logger = AgentLogger(base_log_dir="logs")

    # Start a step
    logger.start_step("Test instruction")

    # Log a screenshot
    test_img = Image.new("RGB", (800, 600), color="white")
    screenshot_path = logger.log_screenshot(test_img)

    # Log an action
    test_code = """
    # Click the search box
    pyautogui.click(300, 210)  # Click the search box
    time.sleep(0.5)

    # Enter search text
    pyautogui.write('news')
    time.sleep(0.5)

    # Click the search button
    pyautogui.moveTo(750, 210)
    pyautogui.click()  # Click the search button
    """
    logger.log_action(test_code, "I need to click the search box and enter text")

    # Log execution result
    logger.log_execution_result(
        {"status": True, "executed": True, "details": "Code executed successfully"}
    )

    # Mark clicks on the screenshot
    logger.mark_screenshot_with_clicks()

    # End the session
    logger.end_session()

    print(f"Logs have been saved to: {logger.session_dir}")
