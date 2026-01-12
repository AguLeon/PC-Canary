#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task09: Create a linked research note."""

import os
from typing import Dict, Any, Optional, List

note_relative_path = "Research/AutomationIdeas.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
note_title = "# Automation Ideas"
link_target = "[[Ideas]]"
summary_text = "These are the automation concepts worth exploring."

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_linked_note"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, note_title, link_target, summary_text
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    note_title = task_parameter.get("note_title", note_title)
    link_target = task_parameter.get("link_target", link_target)
    summary_text = task_parameter.get("summary_text", summary_text)

def _evaluate_linked_note() -> List[Dict[str, Any]]:
    target_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "note_missing",
            "message": f"Linked note '{note_relative_path}' not found"
        }]

    with open(target_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    missing_parts = []
    if note_title and note_title not in content:
        missing_parts.append("title")
    if summary_text and summary_text not in content:
        missing_parts.append("summary")
    if link_target and link_target not in content:
        missing_parts.append("link")

    if missing_parts:
        return [{
            "status": "error",
            "type": "content_missing",
            "message": f"Linked note missing components: {', '.join(missing_parts)}"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": "Linked research note created"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_linked_note":
        return _evaluate_linked_note()
    return None
