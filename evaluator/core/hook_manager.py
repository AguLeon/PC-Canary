from typing import List, Dict, Any, Optional, Callable
import os
import frida
import logging
import time
import signal
import subprocess


class HookManager:
    """
    Hook manager responsible for loading and managing Frida scripts
    """

    def __init__(self, app_path: str = None, app_working_cwd: Optional[str] = None,
                 args: List[str] = None, logger: Optional[logging.Logger] = None,
                 evaluate_on_completion: bool = False):
        """
        Initialize hook manager

        Args:
            logger: Logger instance, uses default if None
        """
        self.scripts = []  # Script path list
        self.app_path = app_path  # Application path
        self.app_working_cwd = app_working_cwd if app_working_cwd else os.getcwd()
        self.frida_session = None  # Frida session
        self.loaded_scripts = []  # Loaded script objects
        self.message_handler = None  # Message handler function
        self.logger = logger
        self.args = args
        self.app_process = None
        self.evaluate_on_completion = evaluate_on_completion
        self.app_started = False
        self.eval_handler = None
        
    def add_script(self, hooker_path: str, dep_script_list: list) -> None:
        """
        Add hook script

        Args:
            task_id: Script path
        """
        if os.path.exists(hooker_path):
            self.scripts.append((hooker_path, dep_script_list))
            self.logger.info(f"Added hook script: {hooker_path}")
        else:
            self.logger.error(f"Script file does not exist: {hooker_path}")
    
    
    def load_scripts(self, eval_handler: Callable[[Dict[str, Any], Any], None]) -> bool:
        """
        Load scripts into target process

        Args:
            eval_handler: Task event handler

        Returns:
            bool: Whether loading was successful
        """
        if not self.scripts:
            self.logger.warning("No scripts to load")
            return False

        self.eval_handler = eval_handler
        try:
            # Connect to target process
            self.logger.info(f"Connecting to process: {self.app_process.pid}")
            self.frida_session = frida.attach(self.app_process.pid)

            # Load all scripts
            for (script_path, dep_script_list) in self.scripts:
                try:
                    scripts = []
                    with open(script_path, 'r', encoding="UTF8") as f:
                        scripts.append(f.read())
                    for script in dep_script_list:
                        with open(script, 'r', encoding="UTF8") as f:
                            scripts.append(f.read())
                    script_content = "\n".join(scripts)

                    script = self.frida_session.create_script(script_content)
                    script.on('message', eval_handler)
                    script.load()

                    self.loaded_scripts.append(script)
                    self.logger.info(f"Script loaded successfully: {script_path}")
                except Exception as e:
                    self.logger.error(f"Failed to load script {script_path}: {str(e)}")

            return len(self.loaded_scripts) > 0

        except frida.ProcessNotFoundError:
            self.logger.error(f"Process not found: {self.app_process.pid}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to process: {str(e)}")
            return False
    
    def unload_scripts(self) -> None:
        """
        Unload all scripts
        """
        try:
            if self.evaluate_on_completion:
                self.trigger_evaluate_on_completion()

            for script in self.loaded_scripts:
                script.unload()

            self.loaded_scripts = []

            if self.frida_session:
                self.frida_session.detach()
                self.frida_session = None

            self.logger.info("Scripts unloaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to unload scripts: {str(e)}")
            
    def start_app(self) -> bool:
        # If application path is provided, start the application
        if self.app_path:
            # Check if app_path exists as a file or is a command in PATH
            import shutil
            resolved_path = self.app_path if os.path.exists(self.app_path) else shutil.which(self.app_path)

            if not resolved_path:
                self.logger.error(f"Application path does not exist: {self.app_path}")
                self.app_started = True
                return True

            if self.args is None:
                self.args = []

            # Build complete command line
            cmd = [resolved_path] + self.args

            try:
                # Start application process
                self.logger.info(f"Starting application: {self.app_path}")
                self.app_process = subprocess.Popen(
                    cmd,
                    cwd=self.app_working_cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                self.logger.info(f"Application started successfully, process ID: {self.app_process.pid}")

                # Wait for application window to load
                self.logger.info("Waiting for application window to load...")

                # Linux system: Use xwininfo command to detect window changes
                try:
                    # Get window list before startup
                    windows_before = subprocess.run(["xwininfo", "-root", "-tree"],
                                                stdout=subprocess.PIPE,
                                                text=True).stdout.count('\n')
                    self.logger.info(f"Window count before startup: {windows_before}")

                    # Wait for new window to appear
                    max_wait_time = 30  # Maximum wait 30 seconds
                    start_wait = time.time()
                    window_detected = False

                    while time.time() - start_wait < max_wait_time:
                        windows_current = subprocess.run(["xwininfo", "-root", "-tree"],
                                                    stdout=subprocess.PIPE,
                                                    text=True).stdout.count('\n')
                        if windows_current > windows_before:
                            window_detected = True
                            self.logger.info(f"New window detected, current window count: {windows_current}")
                            # Wait additional 2 seconds to ensure window content is loaded
                            time.sleep(2)
                            break
                        time.sleep(0.5)

                    if not window_detected:
                        self.logger.warning("No new window detected, using default wait time")
                        time.sleep(5)
                except Exception as window_error:
                    self.logger.warning(f"Window detection error: {str(window_error)}, using default wait time")
                    time.sleep(5)
            except Exception as e:
                self.logger.error(f"Failed to start application: {str(e)}")

        self.app_started = True
        return True
    
    def stop_app(self) -> None:
        # Stop application process
        if hasattr(self, 'app_process') and self.app_process:
            try:
                self.logger.info(f"Attempting to gracefully terminate application process (PID: {self.app_process.pid})")

                # Send SIGTERM signal to notify application to prepare for shutdown
                self.app_process.send_signal(signal.SIGTERM)
                self.logger.info("Sent SIGTERM signal, waiting for application response...")

                # Wait for application to close on its own
                try:
                    self.app_process.wait(timeout=10)  # Wait 10 seconds
                    self.logger.info("Application process closed gracefully")
                except subprocess.TimeoutExpired:
                    self.logger.warning("Application did not close within expected time, trying terminate()")
                    self.app_process.terminate()
                    try:
                        self.app_process.wait(timeout=5)
                        self.logger.info("Application process terminated successfully via terminate()")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("Application did not close via terminate(), trying kill()")
                        self.app_process.kill()
                        self.logger.info("Application process forcibly killed via kill()")
            except Exception as e:
                self.logger.error(f"Error while terminating application process: {str(e)}")

    def trigger_evaluate_on_completion(self):
        self.eval_handler({
            "type": "send", "payload": { "event": "evaluate_on_completion" }
        }, None)
