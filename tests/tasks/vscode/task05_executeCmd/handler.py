#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, Callable, List

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:    
    event_type = message.get('event_type')
    logger.info(message)
    expected_dir = task_parameter.get("dir", "/workspace/.mcpworld/vscode/C-Plus-Plus/data_structures")
    expected_cmd = task_parameter.get("cmd", "tree")
    if event_type == "command_execute":
        c_dir = message.get("dir")
        c_cmd = message.get("cmd")
        if c_cmd == expected_cmd and c_dir == expected_dir:
            return [
                {"status": "key_step", "index": 2},
                {"status": "success", "reason": "Command executed in the expected directory"}
            ]
        elif c_cmd.split() == ['cd', '/workspace/.mcpworld/vscode/C-Plus-Plus/data_structures', '&&', 'tree'] and c_dir == "/workspace/.mcpworld/vscode/C-Plus-Plus":
            return [
                {"status": "key_step", "index": 2},
                {"status": "success", "reason": "Command executed in the expected directory"}
            ]
    elif event_type == "create_terminal":
        return [{"status": "key_step", "index": 1}]
    return None
