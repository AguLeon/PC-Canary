/**
 * Inspect the current workspace for pending Git changes and capture the latest commit message.
 * @returns {Promise<{hasChanges: boolean, lastCommitMessage: string | null}>}
 */
async function checkGitStatus() {
    try {
        // 获取当前工作区文件夹
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            return { hasChanges: false, lastCommitMessage: null };
        }

        // 获取第一个工作区文件夹路径
        const workspacePath = workspaceFolders[0].uri.fsPath;

        // 使用VS Code内置的Git扩展API
        const gitExtension = vscode.extensions.getExtension('vscode.git')?.exports;
        if (!gitExtension) {
            return { hasChanges: false, lastCommitMessage: null };
        }

        const api = gitExtension.getAPI(1);
        const repository = api.getRepository(vscode.Uri.file(workspacePath));

        if (!repository) {
            return { hasChanges: false, lastCommitMessage: null };
        }

        // 检查是否有未提交的修改
        const hasChanges = repository.state.workingTreeChanges.length > 0 || 
                          repository.state.indexChanges.length > 0;

        // 获取最近的commit message
        let lastCommitMessage = null;
        const log = await repository.log({ maxEntries: 1 });
        if (log.length > 0) {
            lastCommitMessage = log[0].message;
        }

        return { hasChanges, lastCommitMessage };

    } catch (error) {
        socket.emit("send", {
            'event_type': "error",
            'message': `Failed to inspect the git repository: ${error.message}`
        });
        return { hasChanges: false, lastCommitMessage: null };
    }
}

// Listen for 'evaluate' event
socket.on('evaluate', async () => {
    const { hasChanges, lastCommitMessage } = await checkGitStatus();
    const message1 = hasChanges ? `Workspace still has uncommitted changes` : `Workspace is clean`;
    const message2 = `Latest commit message:\n${lastCommitMessage}`;
    // vscode.window.showInformationMessage(message);
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': `${message1}\n${message2}`,
        'has_changes': hasChanges,
        'last_message': lastCommitMessage
    });
});
