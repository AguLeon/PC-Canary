#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task04: Rename an existing note."""

import os
from typing import Dict, Any, Optional, List

source_note = "MeetingNotes.md"
target_note = "ClientMeeting.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
content_snippet = "Participants: Alice, Bob, Charlie"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_rename"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global source_note, target_note, vault_path, content_snippet
    if not task_parameter:
        return
    source_note = task_parameter.get("source_note", source_note)
    target_note = task_parameter.get("target_note", target_note)
    vault_path = task_parameter.get("vault_path", vault_path)
    content_snippet = task_parameter.get("content_snippet", content_snippet)

def _evaluate_rename() -> List[Dict[str, Any]]:
    source_path = os.path.join(vault_path, source_note)
    target_path = os.path.join(vault_path, target_note)

    if os.path.exists(source_path):
        return [{
            "status": "error",
            "type": "source_still_exists",
            "message": f"Source note '{source_note}' still exists"
        }]

    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "target_missing",
            "message": f"Target note '{target_note}' does not exist"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    if content_snippet not in content:
        return [{
            "status": "error",
            "type": "content_mismatch",
            "message": f"Content snippet not found in '{target_note}'"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": f"Renamed '{source_note}' to '{target_note}'"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_note_rename":
        return _evaluate_rename()
    return None
