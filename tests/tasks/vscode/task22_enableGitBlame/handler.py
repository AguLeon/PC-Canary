#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(message.get('message'))
    if event_type == 'evaluate_on_completion' and message.get('blameon', None):
        return [
            {"status": "key_step", "index": 1},
            {"status": "success", "reason": "Git blame editor decoration enabled"}
        ]
    else:
        return [{"status": "error", "type": "evaluate_on_completion", "message": "Git blame decoration setting is still disabled"}]
