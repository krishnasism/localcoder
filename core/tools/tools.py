from core.tools.shell import Shell
from core.tools.python import PythonTools

READ_ONLY_TOOL_REGISTRATIONS: dict[str, callable] = {
    "change_directory": Shell.change_directory,
    "list_files": Shell.list_files,
    "get_directory_tree": Shell.get_directory_tree,
    "read_file": Shell.read_file,
    "pytest": PythonTools().run_pytest,
    "pytest_with_coverage": PythonTools().run_pytest_with_coverage,
    "setup_python_virtual_env": PythonTools().setup_python_virtual_env,
}
TOOL_REGISTRATIONS: dict[str, callable] = {
    "sed": Shell.sed,
    "write_file": Shell.write_file,
    "find_files": Shell.find_files,
    "search_text_in_files": Shell.search_text_in_files,
    "mkdir": Shell.mkdir,
    "delete_file": Shell.delete_file,
    "move_file": Shell.move_file,
    "copy_file": Shell.copy_file,
    "move_file_to_directory": Shell.move_file_to_directory,
    "append_to_file": Shell.append_to_file,
    "run_shell_command": Shell.run_shell_command,
}

TOOL_REGISTRATIONS.update(READ_ONLY_TOOL_REGISTRATIONS)

FS_READ_ONLY_TOOLS = [
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
            "description": (
                "List files in the current working directory or an optional subdirectory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional relative or absolute directory path to list. "
                            "Defaults to the current working directory."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_directory_tree",
            "description": (
                "Get a tree representation of the current working directory "
                "or an optional subdirectory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional relative or absolute directory path to inspect. "
                            "Defaults to the current working directory."
                        ),
                    }
                },
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
            "name": "pytest",
            "description": (
                "Run pytest on a test file or folder. Prefer this over run_shell_command "
                "for tests. Example argument: tests or tests/test_api.py"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_file_or_folder": {
                        "type": "string",
                        "description": "The test file or folder to run with pytest.",
                    }
                },
                "required": ["test_file_or_folder"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pytest_with_coverage",
            "description": "Run pytest with coverage on a specified test file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_file_or_folder": {
                        "type": "string",
                        "description": "The test file or folder to run with pytest and coverage.",
                    }
                },
                "required": ["test_file_or_folder"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "setup_python_virtual_env",
            "description": "Set up a Python virtual environment and install dependencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "env_name": {
                        "type": "string",
                        "description": "The name of the virtual environment to create.",
                    }
                },
                "required": ["env_name"],
            },
        },
    },
]

FS_TOOLS = FS_READ_ONLY_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "sed",
            "description": (
                "Replace exactly one occurrence of old_string in a file. "
                "old_string must match the file content exactly (including whitespace). "
                "If old_string appears more than once, pass `line` (1-based) to target one line. "
                "Returns EDIT_FAILED when the match is missing or ambiguous."
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
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to write to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files in the current working directory tree by filename pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Substring pattern to match against file names.",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text_in_files",
            "description": "Search for text in all files under the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for in file contents.",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mkdir",
            "description": "Create a directory (and parents if needed) in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the directory to create.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The file to delete.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {
                        "type": "string",
                        "description": "Source file path.",
                    },
                    "dest": {
                        "type": "string",
                        "description": "Destination file path.",
                    },
                },
                "required": ["src", "dest"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {
                        "type": "string",
                        "description": "Source file path.",
                    },
                    "dest": {
                        "type": "string",
                        "description": "Destination file path.",
                    },
                },
                "required": ["src", "dest"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file_to_directory",
            "description": "Move a file into a destination directory, creating the directory if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {
                        "type": "string",
                        "description": "Source file path.",
                    },
                    "dest_dir": {
                        "type": "string",
                        "description": "Destination directory path.",
                    },
                },
                "required": ["src", "dest_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Append content to a file in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The file to append to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to append.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": "Run an arbitrary shell command and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]
