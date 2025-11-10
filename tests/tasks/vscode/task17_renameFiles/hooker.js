/**
 * Gets the root directory of the current workspace.
 * @returns {string | undefined} The workspace root directory path or undefined if no workspace is open.
 */
async function getWorkspaceRoot() {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders && workspaceFolders.length > 0) {
        // Return the first workspace folder's path
        return workspaceFolders[0].uri.fsPath;
    }
    return undefined;
}

getWorkspaceRoot().then((root) => {
    socket.emit("send", {
        'event_type': "get_root_when_start",
        'message': "Captured workspace root at task start",
        'root': root
    });
});

socket.on('evaluate', async () => {
    const root = await getWorkspaceRoot();
    // vscode.window.showInformationMessage(message);
    socket.emit("send", {
        'event_type': "evaluate_on_completion",
        'message': "Captured workspace root at task completion",
        'root': root
    });
});
