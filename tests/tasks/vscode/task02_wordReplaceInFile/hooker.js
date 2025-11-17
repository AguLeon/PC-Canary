/**
 * Reads the content of a file at the specified path.
 * @param {string} path - The file path to read.
 * @returns {string|undefined} The file content or undefined if an error occurs.
 */
const fs = require("fs");

async function readFile(path) {
    try {
        // Check if the file exists
        if (!fs.existsSync(path)) {
            return undefined;
        }

        // Read the content of the file
        const fileContent = fs.readFileSync(path, 'utf8');
        return fileContent;
    } catch (error) {
        return undefined;
    }
}

// Send initial file content after a brief delay to ensure socket is fully connected
// The script is injected during the connect event, so we need to wait for that to complete
setTimeout(() => {
    readFile("/workspace/.mcpworld/vscode/C-Plus-Plus/bubble_sort.cpp").then(origin_file_content => {
        socket.emit("send", {
            event_type: "read_origin_content",
            message: "Captured original file contents at task start",
            content: origin_file_content
        });
    });
}, 100);

// Listen for 'evaluate' event
socket.on('evaluate', async () => {
    socket.emit("send", {
        event_type: "evaluate_on_completion",
        message: "Captured file contents when the task completed"
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
