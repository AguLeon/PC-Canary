#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task02: Delete an existing note."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "Archive/ArchiveMe.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_deletion"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)

def _evaluate_deletion() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [
            {"status": "key_step", "index": 1},
            {
                "status": "success",
                "reason": f"Note '{note_relative_path}' was deleted from {vault_path}"
            }
        ]

    return [{
        "status": "error",
        "type": "note_still_exists",
        "message": f"Note '{note_relative_path}' still exists at {target_path}"
    }]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_note_deletion":
        return _evaluate_deletion()
    return None
