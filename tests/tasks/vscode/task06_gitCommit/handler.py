#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, Callable, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(message.get('message'))
    if event_type == "evaluate_on_completion":
        has_changes = message.get('has_changes')
        last_message = message.get('last_message')
        expected_message = task_parameter.get("commit_message", "fix bugs")
        if not has_changes and expected_message == last_message:
            return [
                {"status": "key_step", "index": 1},
                {"status": "success", "reason": "Repository is clean and commit message matches expectation"}
            ]
        else:
            return [{"status": "error", "type": "evaluate_on_completion", "message": "Repository still has changes or commit message mismatch"}]
    return None
