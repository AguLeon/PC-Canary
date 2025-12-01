#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task06: Move a note into a target folder."""

import os
from typing import Dict, Any, Optional, List

source_note = "Ideas.md"
target_relative_path = "Archive/Ideas.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
content_snippet = "# Ideas"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_move"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global source_note, target_relative_path, vault_path, content_snippet
    if not task_parameter:
        return
    source_note = task_parameter.get("source_note", source_note)
    target_relative_path = task_parameter.get("target_relative_path", target_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    content_snippet = task_parameter.get("content_snippet", content_snippet)

def _evaluate_move() -> List[Dict[str, Any]]:
    original_path = os.path.join(vault_path, source_note)
    target_path = os.path.join(vault_path, target_relative_path)

    if os.path.exists(original_path):
        return [{
            "status": "error",
            "type": "source_still_exists",
            "message": f"Source note '{source_note}' still exists at {original_path}"
        }]

    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "target_missing",
            "message": f"Moved note not found at {target_relative_path}"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    if content_snippet not in content:
        return [{
            "status": "error",
            "type": "content_mismatch",
            "message": f"Content snippet missing from moved note at {target_relative_path}"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": f"Moved '{source_note}' to '{target_relative_path}'"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_note_move":
        return _evaluate_move()
    return None
