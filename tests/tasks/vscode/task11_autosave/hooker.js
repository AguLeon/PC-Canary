/**
 * Asynchronously checks if auto-save is enabled in VS Code.
 * @returns {Promise<boolean>} Resolves to true if auto-save is enabled, false otherwise.
 */
async function isAutoSaveEnabled() {
    const config = await vscode.workspace.getConfiguration('files');
    return config;
}


// Listen for 'evaluate' event
socket.on('evaluate', async () => {
    const config = await isAutoSaveEnabled();
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': "Captured auto save configuration at task completion",
        'config': config
    });
});
