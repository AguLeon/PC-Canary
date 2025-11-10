#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from typing import Dict, Any, Optional, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    file_path = task_parameter.get("file", "doc/js/hello_world.js")
    root = message.get('root', '')
    file_path = os.path.join(root, file_path)
    logger.info(message.get('message'))
    if event_type == "evaluate_on_completion":
        if os.path.exists(file_path):
            return [
                {"status": "key_step", "index": 1},
                {"status": "success", "reason": "File was created inside the workspace"}
            ]
        else:
            return [{"status": "error", "type": "evaluate_on_completion", "message": "File does not exist at the expected location"}]
    return None
