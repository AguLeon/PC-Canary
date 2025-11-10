/**
 * Reads the .vscode/settings.json file from the current workspace and returns its contents as a JSON object.
 * Returns an empty object if the file does not exist or is invalid.
 * @returns {Promise<object>} The JSON contents of settings.json or an empty object
 */
async function readWorkspaceSettings() {
    try {
        // Get the workspace folders
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            return {};
        }
        
        // Use the first workspace folder (multi-root workspaces would need additional handling)
        const workspacePath = workspaceFolders[0].uri;
        // vscode.window.showInformationMessage(workspacePath);
        const settingsFileUri = vscode.Uri.joinPath(workspacePath, '.vscode', 'settings.json');

        // Read the file
        const fileContent = await vscode.workspace.fs.readFile(settingsFileUri);
        const fileContentString = Buffer.from(fileContent).toString('utf8');

        // Parse JSON
        return JSON.parse(fileContentString);
    } catch (error) {
        // Return empty object if file doesn't exist or is invalid
        if (error instanceof vscode.FileSystemError && error.code === 'FileNotFound') {
            return {};
        }
        // Handle JSON parse errors or other issues
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
