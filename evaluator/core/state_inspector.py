from .hook_manager import HookManager
from typing import List, Dict, Any, Optional, Callable
import logging
import os
import importlib

class StateInspector(HookManager):
    """
    Task evaluator based on REST API or app library implementation.
    Responsible for loading evaluation scripts that communicate with the server.

    This evaluation method does not need to handle various asynchronous events.
    """
    def __init__(self, app_path: str = None, app_working_cwd: Optional[str] = None,
                 args: List[str] = None, logger: Optional[logging.Logger] = None,
                 evaluate_on_completion: bool = False):
        super().__init__(app_path, app_working_cwd, args, logger, evaluate_on_completion)
        self.inspector_on_start = []
        self.inspector_on_completion = []
        self.eval_handler = None

    def add_script(self, hooker_path: str, dep_script_list: str) -> None:
        if os.path.exists(hooker_path):
            self.scripts.append((hooker_path, dep_script_list))
            self.logger.info(f"Added hook script: {hooker_path}")
        else:
            self.logger.error(f"Script file does not exist: {hooker_path}")

    def load_scripts(self, eval_handler: Callable[[Dict[str, Any], Any], None]) -> bool:
        self.eval_handler = eval_handler
        if not self.scripts:
            self.logger.warning("No scripts to load")
            return False

        # Load all scripts
        for (script_path, dep_script_list) in self.scripts:
            try:
                dep_script_list.append(script_path)
                for script in dep_script_list:
                    segments = script.split("/")
                    module_path = '.'.join(segments[-5:-1]+[segments[-1].split('.')[0]])
                    script_module = importlib.import_module(module_path)
                    if hasattr(script_module, 'inspector_on_start'):
                        self.inspector_on_start.append(script_module.inspector_on_start)
                        # Get app initial state
                        script_module.inspector_on_start()
                    if hasattr(script_module, 'inspector_on_completion'):
                        self.inspector_on_completion.append(script_module.inspector_on_completion)
                self.loaded_scripts.append((script_path, dep_script_list))
                self.logger.info(f"Script loaded successfully: {script_path}")
            except Exception as e:
                self.logger.error(f"Failed to load script {script_path}: {str(e)}")
        return len(self.loaded_scripts) > 0

    def unload_scripts(self) -> None:
        if self.evaluate_on_completion:
            self.trigger_evaluate_on_completion()
        self.inspector_on_completion.clear()
        self.inspector_on_start.clear()
        self.eval_handler = None
        self.loaded_scripts.clear()
    
    def start_app(self) -> bool:
        return super().start_app()
    
    def stop_app(self) -> None:
        return super().stop_app()
    
    def trigger_evaluate_on_completion(self) -> None:
        self.logger.info("Triggering evaluation on task completion")
        try:
            for f in self.inspector_on_completion:
                f(self.eval_handler)
        except Exception as e:
            self.logger.error(f"Error triggering evaluation on task completion: {str(e)}")
