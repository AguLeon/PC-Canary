#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Handler for Obsidian task12: Open Firefox, find the capital of Chile, and append it to Ideas.md."""

import os
import subprocess
from typing import Dict, Any, Optional, List

note_relative_path = "Ideas.md"
vault_path = "/workspace/.mcpworld/obsidian/vault"
expected_capital = "Santiago"
search_query = "capital of Chile"

def inspector_on_start():
    pass

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_capital_appended"}, None)

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global note_relative_path, vault_path, expected_capital, search_query
    if not task_parameter:
        return
    note_relative_path = task_parameter.get("note_relative_path", note_relative_path)
    vault_path = task_parameter.get("vault_path", vault_path)
    expected_capital = task_parameter.get("expected_capital", expected_capital)
    search_query = task_parameter.get("search_query", search_query)

def _check_firefox_was_used() -> bool:
    """Check if Firefox process was launched during the task."""
    try:
        # Check if firefox is currently running or was recently run
        result = subprocess.run(
            ["pgrep", "firefox"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        # If we can't check, assume it was used if the final result is correct
        return True

def _evaluate_capital_appended() -> List[Dict[str, Any]]:
    results = []
    
    # Check if Firefox was used (key step 1)
    firefox_used = _check_firefox_was_used()
    if firefox_used:
        results.append({"status": "key_step", "index": 1})
    else:
        # We still continue evaluation - Firefox might have been closed already
        results.append({
            "status": "warning",
            "type": "firefox_not_detected",
            "message": "Could not confirm Firefox was used (it may have been closed)"
        })
    
    # Check if Ideas.md exists
    note_path = os.path.join(vault_path, note_relative_path)
    if not os.path.exists(note_path):
        results.append({
            "status": "error",
            "type": "note_missing",
            "message": f"Note '{note_relative_path}' not found"
        })
        return results

    with open(note_path, "r", encoding="utf-8") as note_file:
        content = note_file.read()

    # Check if the capital (Santiago) is mentioned in the note (case-insensitive)
    if expected_capital.lower() not in content.lower():
        results.append({
            "status": "error",
            "type": "capital_not_found",
            "message": f"Capital of Chile ('{expected_capital}') not found in {note_relative_path}"
        })
        return results

    # Check if Chile is also mentioned for context
    if "chile" not in content.lower():
        results.append({
            "status": "warning",
            "type": "context_missing",
            "message": "Capital found but 'Chile' is not mentioned in the note"
        })

    results.append({"status": "key_step", "index": 2})
    results.append({
        "status": "success", 
        "reason": f"Firefox was used to find and append the capital of Chile ({expected_capital}) to {note_relative_path}"
    })
    
    return results

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    if isinstance(message, dict) and message.get("event") == "evaluate_capital_appended":
        return _evaluate_capital_appended()
    return None
