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
    "apply_patch": Shell.apply_patch,
    "search_replace": Shell.search_replace,
    "replace_lines": Shell.replace_lines,
    "sed": Shell.sed,
    "insert_after": Shell.insert_after,
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
            "description": (
                "Read the contents of a file relative to the current working directory. "
                "Accepts OS-native or forward-slash paths (e.g. src/app.py or src\\app.py). "
                "Optionally pass start_line/end_line (1-based inclusive) for a window."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": (
                            "Relative or absolute file path. Forward or backslash separators are fine."
                        ),
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional 1-based start line for a partial read.",
                        "minimum": 1,
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional 1-based end line for a partial read.",
                        "minimum": 1,
                    },
                    "line": {
                        "type": "integer",
                        "description": "Optional: return only this 1-based line.",
                        "minimum": 1,
                    },
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
            "name": "apply_patch",
            "description": (
                "Preferred edit tool. Apply a simplified unified / Codex-style patch. "
                "One call may update multiple files and include multiple @@ hunks. "
                "Use *** Update File: path and *** Add File: path headers, or pass "
                "filename= with a bare hunk body for a single file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patch": {
                        "type": "string",
                        "description": (
                            "Patch text, e.g.\n"
                            "*** Begin Patch\n"
                            "*** Update File: src/App.tsx\n"
                            "@@\n context\n-old\n+new\n"
                            "*** Add File: src/new.ts\n"
                            "+line\n"
                            "*** End Patch"
                        ),
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Optional single-file target when patch body has no "
                            "*** Update/Add File headers."
                        ),
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, validate only and do not write files.",
                    },
                },
                "required": ["patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_replace",
            "description": (
                "Secondary edit tool for a single unique string swap. "
                "Tolerates minor whitespace drift. For multiple locations, prefer apply_patch. "
                "Set replace_all=true only when every occurrence should change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The file to modify.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Text to find (unique unless replace_all).",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Optional 1-based line to disambiguate matches.",
                        "minimum": 1,
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "If true, replace every occurrence.",
                    },
                },
                "required": ["filename", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_lines",
            "description": (
                "Replace an inclusive 1-based line range with new_content. "
                "Use after reading the file when you know exact line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "File to modify.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to replace (1-based).",
                        "minimum": 1,
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to replace (1-based, inclusive).",
                        "minimum": 1,
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Replacement text for that range (may be multiple lines).",
                    },
                },
                "required": ["filename", "start_line", "end_line", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_after",
            "description": (
                "Insert new content immediately after a unique marker string in a file. "
                "Best for adding one or more new lines. "
                "For two different insert locations, prefer apply_patch or call insert_after twice."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "File to modify.",
                    },
                    "marker": {
                        "type": "string",
                        "description": "Exact existing text to insert after (must be unique).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text to insert (can be multiple lines).",
                    },
                    "line": {
                        "type": "integer",
                        "description": (
                            "Optional 1-based line that CONTAINS the marker, used only to "
                            "disambiguate when the marker appears more than once. "
                            "Do not pass the destination line of the new content."
                        ),
                        "minimum": 1,
                    },
                },
                "required": ["filename", "marker", "content"],
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
