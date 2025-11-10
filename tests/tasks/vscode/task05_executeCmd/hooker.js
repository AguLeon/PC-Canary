// Listen for command execution in the terminal
vscode.window.onDidStartTerminalShellExecution((event) => {
    // console.log(event.execution.commandLine.value);
    // console.log(event.execution.cwd.path);
    socket.emit("send", {
        'event_type': "command_execute",
        'message': "Detected command execution in the VS Code terminal",
        "cmd": event.execution.commandLine.value,
        "dir": event.execution.cwd.path
    });
});

// Register a listener for when a terminal is opened
vscode.window.onDidOpenTerminal(async (terminal) => {
    // Emit terminal creation event via socket
    socket.emit('send', {
        'event_type': 'create_terminal',
        'message': 'Detected terminal creation'
    });
});
