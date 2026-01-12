#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task11: Take a screenshot and add it to MeetingNotes.md."""

import os
import re
from typing import Dict, Any, Optional, List

note_relative_path = "MeetingNotes.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
screenshot_filename = "screenshot. png"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_screenshot"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, screenshot_filename
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    screenshot_filename = task_parameter.get("screenshot_filename", screenshot_filename)

def _find_screenshot_file() -> Optional[str]:
    """Search for any image file in the vault that could be a screenshot."""
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.lower().endswith(image_extensions):
                return os.path.join(root, file)
    return None


def _evaluate_screenshot() -> List[Dict[str, Any]]:
    results = []
    # Check if screenshot image exists in vault
    screenshot_path = _find_screenshot_file()
    if not screenshot_path:
        return [{
            "status": "error",
            "type": "screenshot_missing",
            "message": "No screenshot image file found in the vault"
        }]
    results.append({"status": "key_step", "index": 1})
    # Check if MeetingNotes.md exists
    note_path = os.path.join(vault_path, note_relative_path)
    if not os. path.exists(note_path):
        results.append({
            "status": "error",
            "type": "note_missing",
            "message": f"Note '{note_relative_path}' not found"
        })
        return results

    with open(note_path, "r", encoding="utf-8") as note_file:
        content = note_file. read()

    # Check if note contains an image embed (Markdown or Obsidian syntax)
    # Markdown: ![alt](image.png) or Obsidian: ! [[image.png]]
    markdown_image_pattern = r"!\[.*?\]\(.*?\.(png|jpg|jpeg|gif|bmp|webp).*?\)"
    obsidian_image_pattern = r"!\[\[.*?\.(png|jpg|jpeg|gif|bmp|webp).*?\]\]"
    has_markdown_image = re.search(markdown_image_pattern, content, re.IGNORECASE)
    has_obsidian_image = re.search(obsidian_image_pattern, content, re.IGNORECASE)
    if not has_markdown_image and not has_obsidian_image:
        results.append({
            "status": "error",
            "type": "image_not_embedded",
            "message": "No image reference found in MeetingNotes.md"
        })
        return results

    results.append({"status": "key_step", "index": 2})
    results.append({"status": "success", "reason": "Screenshot taken and embedded in MeetingNotes.md"})
    return results


def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_screenshot":
        return _evaluate_screenshot()
    return None
