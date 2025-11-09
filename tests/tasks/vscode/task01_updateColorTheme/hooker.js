// vscode.window.showInformationMessage('Code injected successfully');
// Reserve an evaluate event hook so the evaluator can request final state
socket.on("evaluate", () => {
    try {
        console.log("[hooker] evaluate event triggered");
        const currentTheme = vscode.workspace.getConfiguration('workbench').get('colorTheme');
        socket.emit("send", {
            "event_type": "evaluate_on_completion", // specific event identifier
            "message": "VSCode theme at task completion: " + currentTheme,
            "data": currentTheme
        });
        console.log("[hooker] emitted evaluate_on_completion", currentTheme);
    } catch (err) {
        console.error("[hooker] failed during evaluate handler", err);
    }
});
