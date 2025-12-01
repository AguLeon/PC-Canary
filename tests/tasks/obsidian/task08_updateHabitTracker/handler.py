#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task08: Update the meditation line in the habit tracker."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "HabitTracker.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
original_line = "- Meditation: 0/7"
updated_line = "- Meditation: 1/7"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_habit_tracker"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, original_line, updated_line
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    original_line = task_parameter.get("original_line", original_line)
    updated_line = task_parameter.get("updated_line", updated_line)

def _evaluate_habit_tracker() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "note_missing",
            "message": f"Habit tracker note '{note_relative_path}' not found"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    if original_line and original_line in content:
        return [{
            "status": "error",
            "type": "original_line_present",
            "message": "Meditation line still shows original value"
        }]

    if updated_line not in content:
        return [{
            "status": "error",
            "type": "updated_line_missing",
            "message": "Updated meditation line not found"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": "Meditation habit updated"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_habit_tracker":
        return _evaluate_habit_tracker()
    return None
