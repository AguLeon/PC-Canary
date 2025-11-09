from typing import List, Dict, Any, Optional, Callable
import os
import logging
import eventlet
import socketio
from multiprocessing import Process, Manager
import threading
import time
import signal
import subprocess

class IpcInjector:
    """
    IPC-based app code injection manager, responsible for loading and managing injected scripts
    """
    def start_server(self, shared_dict):
        # Server function for the child process
        # Ignore SIGINT so Ctrl+C in the parent doesn't kill the socket bridge
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass

        sio = socketio.Server(
            async_mode="eventlet",
            cors_allowed_origins='*',
            allow_upgrades=True,
            ping_timeout=60,
            ping_interval=25
        )
        app = socketio.WSGIApp(sio)
        # Don't rely on the logger from the parent process in the child process to avoid triggering BrokenPipe when the process ends
        logger = None

        def _safe_log(level: str, message: str) -> None:
            print(f"[ipc_injector] {message}")

        @sio.event
        def connect(sid, _):
            _safe_log("info", f"Client attempting to connect: {sid}")

            # First, try to register the session ID
            try:
                shared_dict['target_session_id'].append(sid)
                _safe_log("info", f"Client app connected to server: {sid}")
            except (BrokenPipeError, Exception) as exc:
                # Even if we can't write to shared_dict, accept the connection
                # The session will be tracked when load_scripts is called
                _safe_log("warning", f"Unable to write session to shared_dict: {exc}, but connection accepted")

            # Try to inject any existing scripts, but don't fail if we can't read them
            try:
                scripts_snapshot = list(shared_dict['scripts'])
                _safe_log("info", f"Found {len(scripts_snapshot)} scripts to inject")

                for (p, l) in scripts_snapshot:
                    try:
                        s = []
                        with open(p, 'r', encoding="UTF8") as f:
                            s.append(f.read())
                        for i in l:
                            with open(i, 'r', encoding="UTF8") as f:
                                s.append(f.read())
                        c = "\n".join(s)
                        sio.emit('inject', c, to=sid)
                        _safe_log("info", f"Successfully injected script into {sid}")
                    except Exception as exc:
                        _safe_log("error", f"Failed to send script to {sid}: {exc}")
            except (BrokenPipeError, Exception) as exc:
                # If we can't read scripts now, they'll be injected later via load_scripts
                _safe_log("warning", f"Unable to read scripts on connection: {exc}, will inject later through load_scripts")

            # Log current sessions for debugging
            try:
                current_sessions = list(shared_dict['target_session_id'])
                _safe_log("info", f"Current connected sessions: {current_sessions}")
            except:
                pass

            # Always accept the connection
            return True

        @sio.event
        def send(sid, message):
            # Put the message into the queue for the main process to handle
            _safe_log("info", f"App sending message to evaluator: {message.get('event_type', 'unknown')}")
            try:
                shared_dict['msg_from_app'].append({
                    'type': 'message',
                    'content': message
                })
                _safe_log("info", "Message added to queue")
            except (BrokenPipeError, Exception) as exc:
                _safe_log("error", f"Unable to add message to queue: {exc}")

        def process_message_queue():
            # Function to process the message queue once
            try:
                if shared_dict['msg_from_evaluator']:
                    for msg in shared_dict['msg_from_evaluator']:
                        _safe_log("debug", f"process_message_queue processing message: {msg}")
                        if msg['type'] == 'inject' and 'sid' in msg and 'content' in msg:
                            _safe_log("info", f"Sending inject message to {msg['sid']}")
                            sio.emit('inject', msg['content'], to=msg['sid'])
                        elif msg['type'] == 'evaluate' and 'sid' in msg:
                            _safe_log("info", f"socketio emit evaluate -> {msg['sid']}")
                            sio.emit('evaluate', to=msg['sid'])
                        else:
                            _safe_log("warning", f"Invalid message format or missing sid: {msg}")
                    shared_dict['msg_from_evaluator'][:] = []
            except BrokenPipeError as e:
                _safe_log("error", f"Error processing message (broken pipe), stopping message loop: {e}")
                return
            except Exception as e:
                _safe_log("error", f"Error processing message: {str(e)}")
            # Schedule the next execution
            eventlet.spawn_after(0.5, process_message_queue)

        # Start the message processing thread
        try:
            eventlet.spawn_after(1, process_message_queue)
            if logger:
                logger.info("Server started message processing successfully")
        except Exception as e:
            if logger:
                logger.error(f"Error starting message processing: {str(e)}")

        try:
            eventlet.wsgi.server(eventlet.listen(('', 5000)), app, log_output=False)
        except Exception as e:
            if logger:
                logger.error(f"Server running error: {str(e)}")


    def __init__(self, app_path: str = None, args: List[str] = None, logger: Optional[logging.Logger] = None, evaluate_on_completion: bool = False):
        self.logger = logger
        self.app_path = app_path
        self.args = args

        # Check if port 5000 is already in use and try to free it
        try:
            import socket as sock
            s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('localhost', 5000))
            s.close()
            if result == 0:
                # Port is in use, try to kill any orphaned processes
                if self.logger:
                    self.logger.warning("Port 5000 is occupied, trying to clean up old processes")
                try:
                    subprocess.run(['fuser', '-k', '5000/tcp'],
                                 capture_output=True, timeout=5)
                    time.sleep(1)
                except:
                    pass
        except:
            pass

        # Create process manager
        if self.logger:
            self.logger.debug("Creating multiprocessing Manager")
        self.manager = Manager()

        # Create shared dictionary
        if self.logger:
            self.logger.debug("Creating shared dictionary and lists")
        self.shared_dict = self.manager.dict({
            'scripts': self.manager.list(),
            'loaded_scripts': self.manager.list(),
            'target_session_id': self.manager.list(),
            'msg_from_evaluator': self.manager.list(),
            'msg_from_app': self.manager.list(),
            "evaluate_on_completion": evaluate_on_completion,
        })

        self.on_message = None

        # Create and start server process
        if self.logger:
            self.logger.debug("Starting Socket.IO server child process")
        self.server = Process(
            target=self.start_server,
            args=[self.shared_dict]
        )
        self.server.daemon = False  # Ensure server stays alive
        self.server.start()

        # Give the server time to start and bind to port
        time.sleep(1)
        if self.logger:
            self.logger.info(f"Socket.IO server started (PID: {self.server.pid})")

        # Start message handling thread
        if self.logger:
            self.logger.debug("Starting message handling thread")
        self.message_handler = threading.Thread(target=self._handle_messages)
        self.message_handler.daemon = False  # Keep thread alive
        self.message_handle_running = True
        self.message_handler.start()

        self.app_connect = False
        self.app_process = None
        self.evaluate_on_completion = evaluate_on_completion
        self.triggered_evaluate = False
        self.app_started = False

        if self.logger:
            self.logger.info("IpcInjector initialization complete")

    def trigger_evaluate_on_completion(self):
        """
        Trigger evaluation when task operation is completed, the interface ensures it's an evaluate.
        """
        # Trigger task completion evaluation when the task operation is done
        sessions = list(self.shared_dict['target_session_id'])
        self.logger.info(
            "Triggering evaluation upon task completion (connected_sessions=%s, evaluate_already_triggered=%s)",
            sessions,
            self.triggered_evaluate,
        )
        if not sessions:
            self.logger.warning("No available session id, evaluate message cannot be sent")
        for sid in sessions:
            self.shared_dict['msg_from_evaluator'].append({
                'type': 'evaluate',
                'sid': sid
            })
            if self.logger:
                self.logger.info(f"Sending evaluate message to {sid}")
        # Wait for evaluation to complete
        max_wait_time = 10
        start_wait = time.time()
        while time.time() - start_wait < max_wait_time:
            if self.triggered_evaluate:
                self.logger.info("Task evaluation completed")
                break
            time.sleep(0.5)

    def _handle_messages(self):
        # Handle messages from child process
        while self.message_handle_running:
            try:
                for message in self.shared_dict['msg_from_app']:
                    if message['type'] == 'message':
                        if self.logger:
                            self.logger.info(f"handle_messager received message: {message['content']}")
                        if message["content"].get("event_type") == "start_success":
                            # Application's rendering process or plugin started successfully
                            self.app_connect = True
                            if self.logger:
                                self.logger.info("Application successfully connected to the socket service")
                        elif self.on_message:
                            self.on_message(message['content'], None)
                            if message["content"].get("event_type") == "evaluate_on_completion":
                                self.triggered_evaluate = True
                                if self.logger:
                                    self.logger.info("Received evaluate_on_completion event, marked evaluation as completed")
                self.shared_dict['msg_from_app'] = self.manager.list()
            except BrokenPipeError:
                break
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error handling message: {str(e)}")
            time.sleep(0.5)

    def add_script(self, hooker_path: str, dep_script_list: str) -> None:
        if os.path.exists(hooker_path):
            self.shared_dict['scripts'].append((hooker_path, dep_script_list))
            if self.logger:
                self.logger.info(f"Added hook script: {hooker_path}")
        else:
            if self.logger:
                self.logger.error(f"Script file does not exist: {hooker_path}")
    
    def load_scripts(self, eval_handler: Callable[[Dict[str, Any], Any], None]) -> bool:
        self.on_message = eval_handler
        if not self.shared_dict['scripts']:
            if self.logger:
                self.logger.warning("No scripts to load")
            return False
    
        if not self.shared_dict['target_session_id']:
            if self.logger:
                self.logger.warning(f"Target app cannot connect, {self.shared_dict['target_session_id']}")
            return False

        try:
            success = False
            for (script_path, dep_script_list) in self.shared_dict['scripts']:
                try:
                    scripts = []
                    with open(script_path, 'r', encoding="UTF8") as f:
                        scripts.append(f.read())
                    for script in dep_script_list:
                        with open(script, 'r', encoding="UTF8") as f:
                            scripts.append(f.read())
                    script_content = "\n".join(scripts)
                    
                    # Send the inject command to all connected clients
                    for sid in self.shared_dict['target_session_id']:
                        self.shared_dict['msg_from_evaluator'].append({
                            'type': 'inject',
                            'sid': sid,
                            'content': script_content
                        })
                    
                    self.shared_dict['loaded_scripts'].append((script_path, dep_script_list))
                    success = True
                    if self.logger:
                        self.logger.info(f"Script loaded successfully: {script_path}, {self.shared_dict['target_session_id']}")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to load script {script_path}: {str(e)}")
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to connect to process: {str(e)}")
            return False
        
    def unload_scripts(self) -> None:
        try:
            if self.evaluate_on_completion:
                self.trigger_evaluate_on_completion()

            self.shared_dict['loaded_scripts'] = self.manager.list()
            self.shared_dict['target_session_id'] = self.manager.list()
            self.message_handle_running = False
            # Terminate the server process
            if self.server.is_alive():
                self.server.terminate()
                self.server.join(timeout=5)
            
            # Clean up the manager
            self.manager.shutdown()
            
        except Exception as e:
            if self.logger:

                self.logger.error(f"Failed to unload scripts: {str(e)}")

    def start_app(self) -> bool:
        # If an application path is provided, start the application
        if self.app_path and os.path.exists(self.app_path):
            self.app_path = self.app_path
            if self.args is None:
                self.args = []
        
            # Build the full command line
            cmd = [self.app_path] + self.args

            try:
                # Start the application process
                self.logger.info(f"Starting application: {self.app_path}")

                # Copy parent environment and ensure DISPLAY is set
                env = os.environ.copy()
                if 'DISPLAY' not in env:
                    env['DISPLAY'] = ':4'  # VNC display (TurboVNC)
                # Set XAUTHORITY for X11 authentication
                if 'XAUTHORITY' not in env:
                    env['XAUTHORITY'] = '/home/agent/.Xauthority'

                # Debug: Log the exact command and key environment variables
                self.logger.debug(f"Start command: {' '.join(cmd)}")
                self.logger.debug(f"DISPLAY={env.get('DISPLAY')}, XAUTHORITY={env.get('XAUTHORITY')}")

                # Execute bash script with proper argument passing
                # Prepend 'bash' to execute the script file with its arguments
                bash_cmd = ['/bin/bash'] + cmd
                self.logger.debug(f"Actual command to execute: {' '.join(bash_cmd)}")

                # Don't capture stderr so DEBUG messages go to terminal/logs immediately
                self.app_process = subprocess.Popen(
                    bash_cmd,
                    stdout=subprocess.PIPE,
                    stderr=None,  # Let stderr pass through to terminal
                    env=env
                )

                self.logger.info(f"Application started successfully, Process ID: {self.app_process.pid}")

                # Check process status immediately
                time.sleep(0.5)
                poll_result = self.app_process.poll()
                if poll_result is not None:
                    stdout, _ = self.app_process.communicate(timeout=1)
                    self.logger.error(f"Process exited immediately, return code: {poll_result}")
                    self.logger.error(f"STDOUT: {stdout.decode('utf-8', errors='ignore') if stdout else '(empty)'}")
                    self.logger.error("STDERR: (not captured, check terminal output)")
                else:
                    self.logger.debug(f"Process still running (PID: {self.app_process.pid})")

                # Wait for the application window to load
                self.logger.info("Waiting for the application window to load...")

                # Check what child processes were spawned
                try:
                    children_result = subprocess.run(
                        ["ps", "--ppid", str(self.app_process.pid), "-o", "pid,cmd"],
                        capture_output=True, text=True, timeout=2
                    )
                    if children_result.stdout.strip():
                        self.logger.debug(f"Child processes list:\n{children_result.stdout}")
                except Exception as e:
                    self.logger.warning(f"Failed to get child process list: {e}")

                # On Linux: use xwininfo command to detect window changes
                try:
                    # Get the window list before starting
                    windows_before = subprocess.run(["xwininfo", "-root", "-tree"], 
                                                    stdout=subprocess.PIPE, 
                                                    text=True).stdout.count('\n')
                    self.logger.info(f"Number of windows before start: {windows_before}")

                    # Wait for a new window to appear
                    max_wait_time = 30  # Maximum wait time 30 seconds
                    start_wait = time.time()
                    window_detected = False

                    while time.time() - start_wait < max_wait_time:
                        windows_current = subprocess.run(["xwininfo", "-root", "-tree"], 
                                                        stdout=subprocess.PIPE, 
                                                        text=True).stdout.count('\n')
                        if windows_current > windows_before:
                            window_detected = True
                            self.logger.info(f"New window detected, current window count: {windows_current}")
                            # Wait an additional 2 seconds to ensure window content is loaded
                            time.sleep(2)
                            break
                        time.sleep(0.5)

                    if not window_detected:
                        self.logger.warning("No new window detected, using default wait time")
                        time.sleep(5)
                except Exception as window_error:
                    self.logger.warning(f"Error detecting window: {str(window_error)}. Using default wait time")
                    time.sleep(5)
                
                # Wait for the rendering process or plugin to start
                try:
                    max_wait_time = 600
                    start_wait = time.time()
                    while time.time() - start_wait < max_wait_time:
                        if self.app_connect:
                            self.logger.info("Application successfully connected to socket service")
                            break
                        if self.shared_dict['target_session_id']:
                            if not self.app_connect:
                                self.logger.info(
                                    "Detected client connected to socket, but 'start_success' not sent yet; treating as connected"
                                )
                                self.app_connect = True
                            break
                        time.sleep(0.5)
                    if not self.app_connect:
                        self.logger.warning("No application connection detected to socket service")
                except Exception as e:
                    self.logger.error(f"Application socket connection failed: {str(e)}")
            except Exception as e:
                self.logger.error(f"Application start failed: {str(e)}")
        elif self.app_path:
            self.logger.error(f"Application path does not exist: {self.app_path}")

        self.app_started = True
        return True
    
    def stop_app(self) -> None:
        # Stop the application process
        if hasattr(self, 'app_process') and self.app_process:
            try:
                self.logger.info(f"Attempting to gracefully terminate application process (PID: {self.app_process.pid})")

                # Send SIGTERM signal to inform the app to close
                self.app_process.send_signal(signal.SIGTERM)
                self.logger.info("SIGTERM signal sent, waiting for application response...")

                # Wait for the application to close itself
                try:
                    self.app_process.wait(timeout=10)  # Wait for 10 seconds
                    self.logger.info("Application process closed on its own")
                except subprocess.TimeoutExpired:
                    self.logger.warning("Application did not close within the expected time, attempting to terminate()")
                    self.app_process.terminate()
                    try:
                        self.app_process.wait(timeout=5)
                        self.logger.info("Application process terminated successfully via terminate()")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("Application could not close via terminate(), attempting to kill()")
                        self.app_process.kill()
                        self.logger.info("Application process forcibly terminated via kill()")
            except Exception as e:
                self.logger.error(f"Error while terminating the application process: {str(e)}")
