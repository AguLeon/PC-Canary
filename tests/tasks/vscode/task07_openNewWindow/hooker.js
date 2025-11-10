/**
 * Get the list of workspace folder paths that are currently open in this VS Code instance.
 * @returns {Promise<string[]>} Array of workspace paths
 */
async function getWorkspacePaths() {
    try {
        // 获取当前 VS Code 实例的所有工作区文件夹
        const workspaceFolders = vscode.workspace.workspaceFolders || [];

        // 提取工作区路径并去重
        const uniqueWorkspacePaths = [...new Set(
            workspaceFolders.map(folder => folder.uri.fsPath)
        )];

        return uniqueWorkspacePaths;
    } catch (error) {
        throw new Error(`Failed to read workspace paths: ${error.message}`);
    }
}

getWorkspacePaths().then(work_spaces => {
    socket.emit("send", {
        'event_type': "get_work_spaces",
        'message': "Collected workspace folders when the task started",
        'work_spaces': work_spaces
    });
});

// Listen for 'evaluate' event
socket.on('evaluate', async () => {
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': "Task failed"
    });
});
