#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task03: Append text to an existing note."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "Projects/ProjectPlan.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
append_text = "\n## Summary\nProject plan reviewed and updated."

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_append"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, append_text
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    append_text = task_parameter.get("append_text", append_text)

def _evaluate_append() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "note_missing",
            "message": f"Note '{note_relative_path}' not found at {target_path}"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    if content.rstrip().endswith(append_text.rstrip()):
        return [
            {"status": "key_step", "index": 1},
            {"status": "success", "reason": "Summary text appended to note"}
        ]

    return [{
        "status": "error",
        "type": "append_text_missing",
        "message": f"Appended text not found at the end of '{note_relative_path}'"
    }]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_note_append":
        return _evaluate_append()
    return None
