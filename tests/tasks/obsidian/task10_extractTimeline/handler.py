#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task10: Extract the Upcoming Milestones section."""

import os
from typing import Dict, Any, Optional, List

source_note = "Projects/ProjectPlan.md"
target_note = "Projects/Timeline.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
section_heading = "## Upcoming Milestones"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_timeline_extraction"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global source_note, target_note, vault_path, section_heading
    if not task_parameter:
        return
    source_note = task_parameter.get("source_note", source_note)
    target_note = task_parameter.get("target_note", target_note)
    vault_path = task_parameter.get("vault_path", vault_path)
    section_heading = task_parameter.get("section_heading", section_heading)

def _extract_section_text(content: str, heading: str) -> Optional[str]:
    if heading not in content:
        return None
    lines = content.splitlines()
    collecting = False
    collected: List[str] = []
    for line in lines:
        if not collecting and line.strip() == heading.strip():
            collecting = True
        if collecting:
            collected.append(line)
            if line.strip().startswith("## ") and line.strip() != heading.strip() and len(collected) > 1:
                collected.pop()  # remove line from next section
                break
    section_text = "\n".join(collected).strip()
    return section_text or None

def _evaluate_timeline() -> List[Dict[str, Any]]:
    source_path = os.path.join(vault_path, source_note)
    target_path = os.path.join(vault_path, target_note)

    if not os.path.exists(source_path):
        return [{
            "status": "error",
            "type": "source_missing",
            "message": f"Source note '{source_note}' not found"
        }]

    with open(source_path, "r", encoding="utf-8") as src_file:
        source_content = src_file.read()

    section_text = _extract_section_text(source_content, section_heading)
    if not section_text:
        return [{
            "status": "error",
            "type": "section_missing",
            "message": f"Heading '{section_heading}' not found in source note"
        }]

    if not os.path.exists(target_path):
        return [{
            "status": "error",
            "type": "target_missing",
            "message": f"Timeline note '{target_note}' not created"
        }]

    with open(target_path, "r", encoding="utf-8") as target_file:
        target_content = target_file.read().strip()

    if target_content != section_text:
        return [{
            "status": "error",
            "type": "section_mismatch",
            "message": "Timeline note content does not match extracted section"
        }]

    if section_heading not in source_content:
        return [{
            "status": "error",
            "type": "heading_removed",
            "message": "Section heading missing from source after extraction"
        }]

    return [
        {"status": "key_step", "index": 1},
        {"status": "success", "reason": "Timeline extracted into separate note"}
    ]

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_timeline_extraction":
        return _evaluate_timeline()
    return None
