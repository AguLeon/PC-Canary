#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handler for Obsidian task01: Create a new note

This handler uses filesystem checks to verify that a note was created.
The agent uses MCP tools to create the note, but evaluation is done via direct filesystem access.
"""

import os
from typing import Dict, Any, Optional, List

# Global variables to store task parameters
note_name = "TestNote.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"


def inspector_on_start():
    """
    Called when the task starts - no action needed for this task
    """
    pass


def inspector_on_completion(eval_handler):
    """
    Called when the task completes - trigger evaluation logic via the handler

    Args:
        eval_handler: Callback function that ultimately invokes message_handler
    """
    eval_handler({"event": "evaluate_note_creation"}, None)


def _check_note_creation() -> List[Dict[str, Any]]:
    """
    Verify the target note exists and return evaluator status updates.
    """
    note_filepath = os.path.join(vault_path, note_name)
    if os.path.exists(note_filepath):
        return [
            {"status": "key_step", "index": 1},
            {"status": "success", "reason": f"Note '{note_name}' created successfully at {note_filepath}"}
        ]

    try:
        existing_files = os.listdir(vault_path) if os.path.exists(vault_path) else []
        files_str = ", ".join(existing_files) if existing_files else "none"
    except Exception:
        files_str = "unable to list"

    return [{
        "status": "error",
        "type": "note_not_found",
        "message": f"Note '{note_name}' not found at {note_filepath}. Existing files: {files_str}"
    }]


def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Dummy handler to satisfy BaseEvaluator

    StateInspector doesn't use this, but BaseEvaluator checks for it.
    This prevents the "No callback function found" warning.

    Args:
        message: Event message
        logger: Logger instance
        task_parameter: Task parameters from config

    Returns:
        None (no messages to process)
    """
    # Update global variables from task parameters if provided
    global note_name, vault_path
    if task_parameter:
        note_name = task_parameter.get("note_name", note_name)
        vault_path = task_parameter.get("vault_path", vault_path)

    event_type = (
        message.get("event") if isinstance(message, dict) else None
    )

    if event_type == "evaluate_note_creation":
        return _check_note_creation()

    return None
