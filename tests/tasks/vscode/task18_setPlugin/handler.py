#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(message)
    expected_value = task_parameter.get("info", task_parameter.get("value", False))
    expected_name = task_parameter.get("plugin_name", "TODO Highlight")
    if event_type == "evaluate_on_completion":
        if expected_value == message.get('info', None) and expected_name in message.get('names', []):
            return [
                {"status": "key_step", "index": 1},
                {"status": "key_step", "index": 2},
                {"status": "success", "reason": "Extension installed and configured as expected"}
            ]
        elif expected_name in message.get('names', []):
            return [
                {"status": "key_step", "index": 1},
                {"status": "error", "type": "evaluate_on_completion", "message": "Extension installed but configuration incorrect"}
            ]
        else:
            return [
                {"status": "error", "type": "evaluate_on_completion", "message": "Extension not detected as installed"}
            ]
    return None
