#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(message)
    if event_type == "evaluate_on_completion":
        extensions = message.get('extensions') or []
        plugin_name = task_parameter.get("plugin_name", 'Even Better TOML')
        if plugin_name in extensions:
            return [
                {"status": "key_step", "index": 1},
                {"status": "success", "reason": "Extension installed successfully"}
            ]
        else:
            return [{"status": "error", "type": "evaluate_on_completion", "message": "Extension not detected in the installed list"}]
    return None
