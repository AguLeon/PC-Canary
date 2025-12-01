#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task05: Create a templated daily note."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "Daily/Daily-2025-01-01.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
template_text = "# Daily Log\n- [ ] Plan the day\n- [ ] Review notes\n- [ ] Capture wins"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_daily_note"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, template_text
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    template_text = task_parameter.get("template_text", template_text)

def _evaluate_daily_note() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "note_missing",
            "message": f"Daily note '{note_relative_path}' not found"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read().strip()

    if content == template_text.strip():
        return [
            {"status": "key_step", "index": 1},
            {"status": "success", "reason": f"Daily note '{note_relative_path}' created with template"}
        ]

    return [{
        "status": "error",
        "type": "content_mismatch",
        "message": f"Daily note '{note_relative_path}' does not match template"
    }]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_daily_note":
        return _evaluate_daily_note()
    return None
