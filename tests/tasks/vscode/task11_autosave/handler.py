#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(f"{message}")
    if event_type == "evaluate_on_completion":
        config = message.get('config')
        expected_save_mode = task_parameter.get("autoSave", task_parameter.get("mode", 'afterDelay'))
        expected_save_delay = task_parameter.get("autoSaveDelay", task_parameter.get("delay", 500))
        if config.get("autoSave") == expected_save_mode and expected_save_delay == config.get("autoSaveDelay"):
            return [
                {"status": "key_step", "index": 1},
                {"status": "success", "reason": "Auto save mode and delay updated for the workspace"}
            ]
        else:
            return [{"status": "error", "type": "evaluate_on_completion", "message": "Auto save configuration does not match expectations"}]
    return None
