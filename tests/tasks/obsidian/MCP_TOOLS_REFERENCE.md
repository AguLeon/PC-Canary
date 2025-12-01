# Obsidian MCP Server Tools Reference

This document lists all available MCP tools for the Obsidian server, used for creating handler.py evaluation logic.

## File Management Tools

### `obsidian_list_files_in_vault`
Lists all files and directories in the root directory of your Obsidian vault.

**Parameters:** None required

**Usage in handler:** Verify file creation at vault root level

---

### `obsidian_list_files_in_dir`
Lists all files and directories that exist in a specific Obsidian directory.

**Parameters:**
- `dirpath` (string, required): Path to list files from (relative to vault root). Empty directories will not be returned.

**Usage in handler:** Check for files in specific subdirectories

---

### `obsidian_get_file_contents`
Return the content of a single file in your vault.

**Parameters:**
- `filepath` (string, required): Path to the relevant file (relative to vault root)

**Usage in handler:** Validate file content matches expected text

---

### `obsidian_batch_get_file_contents`
Return the contents of multiple files in your vault, concatenated with headers.

**Parameters:**
- `filepaths` (array of strings, required): List of file paths to read (relative to vault root)

**Usage in handler:** Efficiently check multiple files at once

---

### `obsidian_append_content`
Append content to a new or existing file in the vault.

**Parameters:**
- `filepath` (string, required): Path to the file (relative to vault root)
- `content` (string, required): Content to append to the file

**Usage in handler:** Not typically used in evaluation (agent tool)

---

### `obsidian_delete_file`
Delete a file or directory from the vault.

**Parameters:**
- `filepath` (string, required): Path to the file or directory to delete (relative to vault root)
- `confirm` (boolean, required): Confirmation to delete the file (must be true)

**Usage in handler:** Cleanup during task setup/teardown

---

## Content Modification Tools

### `obsidian_patch_content`
Insert content into an existing note relative to a heading, block reference, or frontmatter field.

**Parameters:**
- `filepath` (string, required): Path to the file (relative to vault root)
- `operation` (enum, required): One of: `append`, `prepend`, `replace`
- `target_type` (enum, required): One of: `heading`, `block`, `frontmatter`
- `target` (string, required): Target identifier (heading path, block reference, or frontmatter field)
- `content` (string, required): Content to insert

**Usage in handler:** Not typically used in evaluation (agent tool)

---

## Search Tools

### `obsidian_simple_search`
Simple search for documents matching a specified text query across all files in the vault.

**Parameters:**
- `query` (string, required): Text to search for in the vault
- `context_length` (integer, optional): How much context to return around the matching string (default: 100)

**Usage in handler:** Verify specific content exists anywhere in vault

---

### `obsidian_complex_search`
Complex search for documents using a JsonLogic query. Supports standard JsonLogic operators plus 'glob' and 'regexp' for pattern matching.

**Parameters:**
- `query` (object, required): JsonLogic query object
  - Example: `{"glob": ["*.md", {"var": "path"}]}` matches all markdown files

**Usage in handler:** Advanced file filtering (by tags, patterns, metadata)

---

## Periodic Notes Tools

### `obsidian_get_periodic_note`
Get current periodic note for the specified period.

**Parameters:**
- `period` (enum, required): One of: `daily`, `weekly`, `monthly`, `quarterly`, `yearly`

**Usage in handler:** Validate periodic note creation tasks

---

### `obsidian_get_recent_periodic_notes`
Get most recent periodic notes for the specified period type.

**Parameters:**
- `period` (enum, required): One of: `daily`, `weekly`, `monthly`, `quarterly`, `yearly`
- `limit` (integer, optional): Maximum number of notes to return (default: 5, max: 50)
- `include_content` (boolean, optional): Whether to include note content (default: false)

**Usage in handler:** Check recent note history

---

## Recent Changes Tools

### `obsidian_get_recent_changes`
Get recently modified files in the vault.

**Parameters:**
- `limit` (integer, optional): Maximum number of files to return (default: 10, max: 100)
- `days` (integer, optional): Only include files modified within this many days (default: 90)

**Usage in handler:** Verify files were recently created/modified

---

## Common Handler Patterns

### Pattern 1: Check if file exists
```python
result = mcp_call("obsidian_list_files_in_vault", {})
if "MyNote.md" in result:
    return success
```

### Pattern 2: Verify file content
```python
content = mcp_call("obsidian_get_file_contents", {"filepath": "MyNote.md"})
if expected_text in content:
    return success
```

### Pattern 3: Search for specific content
```python
results = mcp_call("obsidian_simple_search", {"query": "expected phrase"})
if len(results) > 0:
    return success
```

### Pattern 4: Check recent changes
```python
recent = mcp_call("obsidian_get_recent_changes", {"limit": 10, "days": 1})
if any(f["path"] == "MyNote.md" for f in recent):
    return success
```
