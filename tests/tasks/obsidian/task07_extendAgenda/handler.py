#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task07: extend the meeting agenda with action items."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "Meetings/Agenda.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
append_text = "\n## Action Items\n- Owner: Alice – Prepare KPI deck\n- Owner: Bob – Gather blocker list\n- Owner: Charlie – Draft sprint goals"
required_heading = "## Agenda"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_agenda_extension"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, append_text, required_heading
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    append_text = task_parameter.get("append_text", append_text)
    required_heading = task_parameter.get("required_heading", required_heading)

def _evaluate_extension() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "note_missing",
            "message": f"Agenda note '{note_relative_path}' not found"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    if required_heading and required_heading not in content:
        return [{
            "status": "error",
            "type": "heading_missing",
            "message": f"Required heading '{required_heading}' not present after edit"
        }]

    if append_text.strip() not in content:
        return [{
            "status": "error",
            "type": "append_text_missing",
            "message": "Action-item block not found in agenda note"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": "Agenda extended with action items"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_agenda_extension":
        return _evaluate_extension()
    return None
