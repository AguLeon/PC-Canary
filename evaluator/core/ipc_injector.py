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
    基于IPC开发的app的代码注入管理器, 负责加载和管理注入脚本
    """
    def start_server(self, shared_dict):
        # 子进程的服务器函数
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
        # 在子进程中不要依赖主进程中的 logger，防止进程结束时触发 BrokenPipe
        logger = None

        def _safe_log(level: str, message: str) -> None:
            print(f"[ipc_injector] {message}")

        @sio.event
        def connect(sid, _):
            _safe_log("info", f"客户端尝试连接: {sid}")

            # First, try to register the session ID
            try:
                shared_dict['target_session_id'].append(sid)
                _safe_log("info", f"客户端app连接到服务器: {sid}")
            except (BrokenPipeError, Exception) as exc:
                # Even if we can't write to shared_dict, accept the connection
                # The session will be tracked when load_scripts is called
                _safe_log("warning", f"无法将 session 写入 shared_dict: {exc}, 但仍接受连接")

            # Try to inject any existing scripts, but don't fail if we can't read them
            try:
                scripts_snapshot = list(shared_dict['scripts'])
                _safe_log("info", f"找到 {len(scripts_snapshot)} 个脚本待注入")

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
                        _safe_log("info", f"成功注入脚本到 {sid}")
                    except Exception as exc:
                        _safe_log("error", f"发送脚本到 {sid} 失败: {exc}")
            except (BrokenPipeError, Exception) as exc:
                # If we can't read scripts now, they'll be injected later via load_scripts
                _safe_log("warning", f"无法在连接时读取脚本: {exc}, 稍后将通过 load_scripts 注入")

            # Log current sessions for debugging
            try:
                current_sessions = list(shared_dict['target_session_id'])
                _safe_log("info", f"当前已连接会话: {current_sessions}")
            except:
                pass

            # Always accept the connection
            return True

        @sio.event
        def send(sid, message):
            # 将消息放入队列，由主进程处理
            _safe_log("info", f"app向评估器发送消息: {message.get('event_type', 'unknown')}")
            try:
                shared_dict['msg_from_app'].append({
                    'type': 'message',
                    'content': message
                })
                _safe_log("info", "消息已加入队列")
            except (BrokenPipeError, Exception) as exc:
                _safe_log("error", f"无法将消息加入队列: {exc}")

        def process_message_queue():
            # 单次处理消息队列的函数
            try:
                if shared_dict['msg_from_evaluator']:
                    for msg in shared_dict['msg_from_evaluator']:
                        _safe_log("debug", f"process_message_queue处理消息: {msg}")
                        if msg['type'] == 'inject' and 'sid' in msg and 'content' in msg:
                            _safe_log("info", f"发送 inject 消息到 {msg['sid']}")
                            sio.emit('inject', msg['content'], to=msg['sid'])
                        elif msg['type'] == 'evaluate' and 'sid' in msg:
                            _safe_log("info", f"socketio emit evaluate -> {msg['sid']}")
                            sio.emit('evaluate', to=msg['sid'])
                        else:
                            _safe_log("warning", f"无效的消息格式或缺少sid: {msg}")
                    shared_dict['msg_from_evaluator'][:] = []
            except BrokenPipeError as e:
                _safe_log("error", f"处理消息错误 (broken pipe), 停止消息循环: {e}")
                return
            except Exception as e:
                _safe_log("error", f"处理消息错误: {str(e)}")
            # 调度下一次执行
            eventlet.spawn_after(0.5, process_message_queue)

        # 启动消息处理线程
        try:
            eventlet.spawn_after(1, process_message_queue)
            if logger:
                logger.info("服务器启动消息处理成功")
        except Exception as e:
            if logger:
                logger.error(f"服务器启动消息处理报错: {str(e)}")

        try:
            eventlet.wsgi.server(eventlet.listen(('', 5000)), app, log_output=False)
        except Exception as e:
            if logger:
                logger.error(f"服务器运行错误: {str(e)}")


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
                    self.logger.warning("端口 5000 已被占用，尝试清理旧进程")
                try:
                    subprocess.run(['fuser', '-k', '5000/tcp'],
                                 capture_output=True, timeout=5)
                    time.sleep(1)
                except:
                    pass
        except:
            pass

        # 创建进程管理器
        if self.logger:
            self.logger.debug("创建 multiprocessing Manager")
        self.manager = Manager()

        # 创建共享字典
        if self.logger:
            self.logger.debug("创建共享字典和列表")
        self.shared_dict = self.manager.dict({
            'scripts': self.manager.list(),
            'loaded_scripts': self.manager.list(),
            'target_session_id': self.manager.list(),
            'msg_from_evaluator': self.manager.list(),
            'msg_from_app': self.manager.list(),
            "evaluate_on_completion": evaluate_on_completion,
        })

        self.on_message = None

        # 创建并启动服务器进程
        if self.logger:
            self.logger.debug("启动 Socket.IO 服务器子进程")
        self.server = Process(
            target=self.start_server,
            args=[self.shared_dict]
        )
        self.server.daemon = False  # Ensure server stays alive
        self.server.start()

        # Give the server time to start and bind to port
        time.sleep(1)
        if self.logger:
            self.logger.info(f"Socket.IO 服务器已启动 (PID: {self.server.pid})")

        # 启动消息处理线程
        if self.logger:
            self.logger.debug("启动消息处理线程")
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
            self.logger.info("IpcInjector 初始化完成")

    def trigger_evaluate_on_completion(self):
        """
        在任务操作完成时触发评估, 预留的接口需要保证是evaluate
        """
        # 在任务操作完毕时触发任务完成的评估
        sessions = list(self.shared_dict['target_session_id'])
        self.logger.info(
            "在任务操作完毕时触发评估 (connected_sessions=%s, evaluate_already_triggered=%s)",
            sessions,
            self.triggered_evaluate,
        )
        if not sessions:
            self.logger.warning("当前没有可用的 session id，evaluate 消息无法发送")
        for sid in sessions:
            self.shared_dict['msg_from_evaluator'].append({
                'type': 'evaluate',
                'sid': sid
            })
            if self.logger:
                self.logger.info(f"发送 evaluate 消息到 {sid}")
        # 等待评估完毕
        max_wait_time = 10
        start_wait = time.time()
        while time.time() - start_wait < max_wait_time:
            if self.triggered_evaluate:
                self.logger.info("任务评估完成")
                break
            time.sleep(0.5)

    def _handle_messages(self):
        # 处理从子进程发来的消息
        while self.message_handle_running:
            try:
                for message in self.shared_dict['msg_from_app']:
                    if message['type'] == 'message':
                        if self.logger:
                            self.logger.info(f"handle_messager收到消息: {message['content']}")
                        if message["content"].get("event_type") == "start_success":
                            # 应用的渲染进程或者插件启动成功
                            self.app_connect = True
                            if self.logger:
                                self.logger.info("应用成功连接到socket服务")
                        elif self.on_message:
                            self.on_message(message['content'], None)
                            if message["content"].get("event_type") == "evaluate_on_completion":
                                self.triggered_evaluate = True
                                if self.logger:
                                    self.logger.info("收到 evaluate_on_completion 事件，标记评估已完成")
                self.shared_dict['msg_from_app'] = self.manager.list()
            except BrokenPipeError:
                break
            except Exception as e:
                if self.logger:
                    self.logger.error(f"处理消息错误: {str(e)}")
            time.sleep(0.5)

    def add_script(self, hooker_path: str, dep_script_list:str) -> None:
        if os.path.exists(hooker_path):
            self.shared_dict['scripts'].append((hooker_path, dep_script_list))
            if self.logger:
                self.logger.info(f"添加钩子脚本: {hooker_path}")
        else:
            if self.logger:
                self.logger.error(f"脚本文件不存在: {hooker_path}")
    
    def load_scripts(self, eval_handler: Callable[[Dict[str, Any], Any], None]) -> bool:
        self.on_message = eval_handler
        if not self.shared_dict['scripts']:
            if self.logger:
                self.logger.warning("没有脚本可加载")
            return False
    
        if not self.shared_dict['target_session_id']:
            if self.logger:
                self.logger.warning(f"目标APP无法连接, {self.shared_dict['target_session_id']}")
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
                    
                    # 向所有已连接的客户端发送注入命令
                    for sid in self.shared_dict['target_session_id']:
                        self.shared_dict['msg_from_evaluator'].append({
                            'type': 'inject',
                            'sid': sid,
                            'content': script_content
                        })
                    
                    self.shared_dict['loaded_scripts'].append((script_path, dep_script_list))
                    success = True
                    if self.logger:
                        self.logger.info(f"加载脚本成功: {script_path}, {self.shared_dict['target_session_id']}")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"加载脚本失败 {script_path}: {str(e)}")
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"连接到进程失败: {str(e)}")
            return False
        
    def unload_scripts(self) -> None:
        try:
            if self.evaluate_on_completion:
                self.trigger_evaluate_on_completion()

            self.shared_dict['loaded_scripts'] = self.manager.list()
            self.shared_dict['target_session_id'] = self.manager.list()
            self.message_handle_running = False
            # 终止服务器进程
            if self.server.is_alive():
                self.server.terminate()
                self.server.join(timeout=5)
            
            # 清理管理器
            self.manager.shutdown()
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"卸载脚本失败: {str(e)}")

    def start_app(self) -> bool:
        #  如果提供了应用路径，则启动应用
        if self.app_path and os.path.exists(self.app_path):
            self.app_path = self.app_path
            if self.args is None:
                self.args = []
        
            # 构建完整的命令行
            cmd = [self.app_path] + self.args

            try:
                # 启动应用进程
                self.logger.info(f"正在启动应用: {self.app_path}")
                # Copy parent environment and ensure DISPLAY is set
                env = os.environ.copy()
                if 'DISPLAY' not in env:
                    env['DISPLAY'] = ':4'  # VNC display (TurboVNC)
                # Set XAUTHORITY for X11 authentication
                if 'XAUTHORITY' not in env:
                    env['XAUTHORITY'] = '/home/agent/.Xauthority'

                # Debug: Log the exact command and key environment variables
                self.logger.debug(f"启动命令: {' '.join(cmd)}")
                self.logger.debug(f"DISPLAY={env.get('DISPLAY')}, XAUTHORITY={env.get('XAUTHORITY')}")

                # Execute bash script with proper argument passing
                # Prepend 'bash' to execute the script file with its arguments
                bash_cmd = ['/bin/bash'] + cmd
                self.logger.debug(f"实际执行命令: {' '.join(bash_cmd)}")

                # Don't capture stderr so DEBUG messages go to terminal/logs immediately
                self.app_process = subprocess.Popen(
                    bash_cmd,
                    stdout=subprocess.PIPE,
                    stderr=None,  # Let stderr pass through to terminal
                    env=env
                )

                self.logger.info(f"应用启动成功，进程ID: {self.app_process.pid}")

                # Check process status immediately
                time.sleep(0.5)
                poll_result = self.app_process.poll()
                if poll_result is not None:
                    stdout, _ = self.app_process.communicate(timeout=1)
                    self.logger.error(f"进程立即退出，返回码: {poll_result}")
                    self.logger.error(f"STDOUT: {stdout.decode('utf-8', errors='ignore') if stdout else '(empty)'}")
                    self.logger.error("STDERR: (not captured, check terminal output)")
                else:
                    self.logger.debug(f"进程仍在运行 (PID: {self.app_process.pid})")

                # 等待应用窗口加载完成
                self.logger.info("等待应用窗口加载完成...")

                # Check what child processes were spawned
                try:
                    children_result = subprocess.run(
                        ["ps", "--ppid", str(self.app_process.pid), "-o", "pid,cmd"],
                        capture_output=True, text=True, timeout=2
                    )
                    if children_result.stdout.strip():
                        self.logger.debug(f"子进程列表:\n{children_result.stdout}")
                except Exception as e:
                    self.logger.warning(f"无法获取子进程列表: {e}")

                # Linux系统：使用xwininfo命令检测窗口变化
                try:
                    # 获取启动前窗口列表
                    windows_before = subprocess.run(["xwininfo", "-root", "-tree"], 
                                                stdout=subprocess.PIPE, 
                                                text=True).stdout.count('\n')
                    self.logger.info(f"启动前窗口行数: {windows_before}")

                    # 等待新窗口出现
                    max_wait_time = 30  # 最大等待30秒
                    start_wait = time.time()
                    window_detected = False

                    while time.time() - start_wait < max_wait_time:
                        windows_current = subprocess.run(["xwininfo", "-root", "-tree"], 
                                                    stdout=subprocess.PIPE, 
                                                    text=True).stdout.count('\n')
                        if windows_current > windows_before:
                            window_detected = True
                            self.logger.info(f"检测到新窗口，当前窗口行数: {windows_current}")
                            # 额外等待2秒确保窗口内容加载完成
                            time.sleep(2)
                            break
                        time.sleep(0.5)

                    if not window_detected:
                        self.logger.warning("未检测到新窗口出现，使用默认等待时间")
                        time.sleep(5)
                except Exception as window_error:
                    self.logger.warning(f"窗口检测出错: {str(window_error)}，使用默认等待时间")
                    time.sleep(5)
                
                # 等待渲染进程或者插件启动
                try:
                    max_wait_time = 600
                    start_wait = time.time()
                    while time.time() - start_wait < max_wait_time:
                        if self.app_connect:
                            self.logger.info("检测到应用成功连接到socket服务")
                            break
                        if self.shared_dict['target_session_id']:
                            if not self.app_connect:
                                self.logger.info(
                                    "检测到客户端已连接 socket，但尚未发送 start_success；将其视为已连接"
                                )
                                self.app_connect = True
                            break
                        time.sleep(0.5)
                    if not self.app_connect:
                        self.logger.warning("没有检测到应用连接socket服务")
                except Exception as e:
                    self.logger.error(f"应用socket连接失败: {str(e)}")
            except Exception as e:
                self.logger.error(f"应用启动失败: {str(e)}")
        elif self.app_path:
            self.logger.error(f"应用路径不存在: {self.app_path}")

        self.app_started = True
        return True
    
    def stop_app(self) -> None:
        # 停止应用进程
        if hasattr(self, 'app_process') and self.app_process:
            try:
                self.logger.info(f"尝试优雅地终止应用进程 (PID: {self.app_process.pid})")

                # 发送SIGTERM信号，通知应用准备关闭
                self.app_process.send_signal(signal.SIGTERM)
                self.logger.info("已发送SIGTERM信号，等待应用响应...")

                # 等待应用自行关闭
                try:
                    self.app_process.wait(timeout=10)  # 等待10秒
                    self.logger.info("应用进程已自行关闭")
                except subprocess.TimeoutExpired:
                    self.logger.warning("应用未在预期时间内关闭，尝试使用terminate()")
                    self.app_process.terminate()
                    try:
                        self.app_process.wait(timeout=5)
                        self.logger.info("应用进程已通过terminate()正常终止")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("应用未能通过terminate()关闭，尝试使用kill()")
                        self.app_process.kill()
                        self.logger.info("应用进程已通过kill()强制终止")
            except Exception as e:
                self.logger.error(f"终止应用进程时出错: {str(e)}")
