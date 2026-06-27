from core.tools.shell import Shell

TOOL_REGISTRATIONS = {
    "change_directory": Shell.change_directory,
    "list_files": Shell.list_files,
    "get_directory_tree": Shell.get_directory_tree,
    "read_file": Shell.read_file,
    "sed": Shell.sed,
}

FS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "Change the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to change the current working directory to.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_directory_tree",
            "description": "Get a tree representation of the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to read.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sed",
            "description": (
                "Replace occurrences of a string in a file. "
                "If a line number is provided, only that line will be modified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to modify.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The string to be replaced.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace with.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "The line number to modify (1-based index).",
                        "minimum": 1,
                    },
                },
                "required": ["filename", "old_string", "new_string"],
            },
        },
    },
]
