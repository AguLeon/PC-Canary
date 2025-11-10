/**
 * 检查git blame editor decoration是否启用
 * @returns {Promise<boolean>} 返回是否启用的布尔值
 */
async function isGitBlameDecorationEnabled() {
    try {
        // 获取VS Code配置
        const config = vscode.workspace.getConfiguration('git');
        
        // 获取git.blame.editorDecoration.enabled设置
        const isEnabled = await config.get('blame.editorDecoration.enabled', false);
        return isEnabled;
    } catch (error) {
        console.error(`Error checking Git blame decoration setting: ${error.message}`);
        return false;
    }
}

socket.on('evaluate', async () => {
    const blame_on = await isGitBlameDecorationEnabled();
    // vscode.window.showInformationMessage(message);
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': "Captured blame decoration setting at task completion",
        'blameon': blame_on
    });
});
