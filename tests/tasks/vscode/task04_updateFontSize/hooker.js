const SETTINGS_FILE_PATH = "/workspace/.mcpworld/vscode/.vscode/settings.json";

/**
 * Reads the sandbox-wide settings.json file and returns its JSON contents.
 * Returns an empty object if the file does not exist or fails to parse.
 */
async function readWorkspaceSettings() {
    try {
        const settingsFileUri = vscode.Uri.file(SETTINGS_FILE_PATH);
        const fileContent = await vscode.workspace.fs.readFile(settingsFileUri);
        const fileContentString = Buffer.from(fileContent).toString("utf8");
        return JSON.parse(fileContentString);
    } catch (error) {
        if (error instanceof vscode.FileSystemError && error.code === "FileNotFound") {
            return {};
        }
        return {};
    }
}

// vscode.window.showInformationMessage(`代码成功注入`);
readWorkspaceSettings().then(settings => {
    socket.emit("send", {
        'event_type': "read_origin_content",
        'message': "Captured initial settings.json contents",
        'data': settings
    });
});

// Listen for 'evaluate' event
socket.on('evaluate', async () => {
    const settings = await readWorkspaceSettings();
    // vscode.window.showInformationMessage(message);
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': "Captured settings.json contents at task completion",
        'data': settings
    });
});

// Register a listener for when a text document is opened
vscode.workspace.onDidOpenTextDocument(async (document) => {
    const filePath = document.uri.fsPath;
    socket.emit("send", {
        event_type: "open_file",
        message: "File opened",
        path: filePath,
        scheme: document.uri.scheme
    });
});
