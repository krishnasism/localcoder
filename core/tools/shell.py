import asyncio
import os
import pathlib
import logging
import re

logger = logging.getLogger(__name__)


class Shell:
    current_directory = os.getcwd()

    @staticmethod
    def _normalize_user_path(path: str) -> str:
        """Convert mixed / and \\ separators to the current OS convention."""
        if not path:
            return path
        # pathlib accepts both separators; normpath makes them OS-native.
        return os.path.normpath(path.replace("/", os.sep).replace("\\", os.sep))

    @staticmethod
    def _resolve_path(path: str) -> str:
        """Resolve a tool path against the agent cwd with OS-native separators."""
        if not path or not str(path).strip():
            return Shell.current_directory

        normalized = Shell._normalize_user_path(str(path).strip())
        if os.path.isabs(normalized):
            return normalized

        return os.path.normpath(os.path.join(Shell.current_directory, normalized))

    @staticmethod
    async def get_parent_folder(path: str) -> str:
        try:

            def _get_parent() -> str:
                return str(pathlib.Path(Shell._resolve_path(path)).parent)

            return await asyncio.to_thread(_get_parent)
        except Exception as e:
            return f"Error getting parent folder: {str(e)}"

    @staticmethod
    def _walk_skip_names() -> set[str]:
        return {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            "dist",
            "build",
            ".next",
            "coverage",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".mypy_cache",
            "out",
            "target",
        }

    @staticmethod
    async def find_files(pattern: str, max_matches: int = 80) -> str:
        try:

            def _find() -> str:
                skip = Shell._walk_skip_names()
                matches: list[str] = []
                for root, dirs, files in os.walk(Shell.current_directory):
                    dirs[:] = [d for d in dirs if d not in skip]
                    for filename in files:
                        if pattern in filename:
                            matches.append(os.path.join(root, filename))
                            if len(matches) >= max_matches:
                                matches.append(
                                    f"... truncated after {max_matches} matches"
                                )
                                return "\n".join(matches)
                return "\n".join(matches)

            return await asyncio.to_thread(_find)
        except Exception as e:
            return f"Error finding files: {str(e)}"

    @staticmethod
    async def search_text_in_files(pattern: str, max_matches: int = 60) -> str:
        try:

            def _search() -> str:
                skip = Shell._walk_skip_names()
                matches: list[str] = []
                for root, dirs, files in os.walk(Shell.current_directory):
                    dirs[:] = [d for d in dirs if d not in skip]
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            with open(file_path, "r", errors="ignore") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if pattern in line:
                                        matches.append(
                                            f"{file_path}:{line_number}: {line.strip()}"
                                        )
                                        if len(matches) >= max_matches:
                                            matches.append(
                                                f"... truncated after {max_matches} matches"
                                            )
                                            return "\n".join(matches)
                        except OSError:
                            continue
                return "\n".join(matches)

            return await asyncio.to_thread(_search)
        except Exception as e:
            return f"Error searching text in files: {str(e)}"

    @staticmethod
    async def mkdir(path: str) -> str:
        try:
            resolved = Shell._resolve_path(path)
            await asyncio.to_thread(os.makedirs, resolved, exist_ok=True)
            return f"Directory '{resolved}' created successfully."
        except Exception as e:
            return f"Error creating directory: {str(e)}"

    @staticmethod
    async def delete_file(filename: str) -> str:
        try:
            resolved = Shell._resolve_path(filename)
            await asyncio.to_thread(os.remove, resolved)
            return f"File '{resolved}' deleted successfully."
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    @staticmethod
    async def move_file(src: str, dest: str) -> str:
        try:
            src_path = Shell._resolve_path(src)
            dest_path = Shell._resolve_path(dest)
            await asyncio.to_thread(os.rename, src_path, dest_path)
            return f"File '{src_path}' moved to '{dest_path}' successfully."
        except Exception as e:
            return f"Error moving file: {str(e)}"

    @staticmethod
    async def copy_file(src: str, dest: str) -> str:
        try:
            import shutil

            src_path = Shell._resolve_path(src)
            dest_path = Shell._resolve_path(dest)
            await asyncio.to_thread(shutil.copy, src_path, dest_path)
            return f"File '{src_path}' copied to '{dest_path}' successfully."
        except Exception as e:
            return f"Error copying file: {str(e)}"

    @staticmethod
    async def move_file_to_directory(src: str, dest_dir: str) -> str:
        try:
            src_path = Shell._resolve_path(src)
            dest_dir_path = Shell._resolve_path(dest_dir)
            await asyncio.to_thread(os.makedirs, dest_dir_path, exist_ok=True)
            dest_path = os.path.join(dest_dir_path, os.path.basename(src_path))
            await asyncio.to_thread(os.rename, src_path, dest_path)
            return (
                f"File '{src_path}' moved to directory '{dest_dir_path}' successfully."
            )
        except Exception as e:
            return f"Error moving file to directory: {str(e)}"

    @staticmethod
    async def append_to_file(filename: str, content: str) -> str:
        try:
            resolved = Shell._resolve_path(filename)

            def _append() -> None:
                with open(resolved, "a") as file:
                    file.write(content)

            await asyncio.to_thread(_append)
            return f"Appended content to {resolved}"
        except Exception as e:
            return f"Error appending to file: {str(e)}"

    @staticmethod
    def _resolve_venv_python() -> str | None:
        for folder in ("venv", ".venv", "agent_venv_default"):
            for scripts in ("Scripts", "bin"):
                candidate = os.path.join(
                    Shell.current_directory, folder, scripts, "python.exe"
                )
                if os.path.isfile(candidate):
                    return candidate
                candidate = os.path.join(
                    Shell.current_directory, folder, scripts, "python"
                )
                if os.path.isfile(candidate):
                    return candidate
        return None

    @staticmethod
    def _normalize_shell_command(command: str) -> str:
        normalized = command.strip()
        venv_python = Shell._resolve_venv_python()

        if venv_python and re.search(r"activate(\.bat|\.ps1)?", normalized, re.I):
            normalized = re.sub(
                r"^.*?(?:activate(?:\.bat|\.ps1)?)\s*(?:&&|;)\s*",
                "",
                normalized,
                flags=re.I,
            )
            normalized = re.sub(
                r"\bpython\b",
                lambda _match: f'"{venv_python}"',
                normalized,
                count=1,
            )
        elif venv_python and normalized.startswith("python "):
            normalized = normalized.replace("python", f'"{venv_python}"', 1)

        if (
            os.name == "nt"
            and "&&" in normalized
            and not normalized.lower().startswith("cmd /c")
        ):
            return f'cmd /c "{normalized}"'
        return normalized

    @staticmethod
    async def run_shell_command(command: str) -> str:
        try:
            normalized = Shell._normalize_shell_command(command)
            process = await asyncio.create_subprocess_shell(
                normalized,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Shell.current_directory,
            )
            stdout, stderr = await process.communicate()
            stdout_text = stdout.decode(errors="ignore") if stdout else ""
            stderr_text = stderr.decode(errors="ignore") if stderr else ""

            if process.returncode == 0:
                output = (stdout_text or stderr_text).strip()
                return output or "Command completed successfully with no output."

            detail = (stderr_text or stdout_text).strip()
            return (
                f"Error executing command (exit {process.returncode}): {detail}"
                if detail
                else f"Error executing command (exit {process.returncode})."
            )
        except Exception as e:
            return f"Error executing shell command: {str(e)}"

    @staticmethod
    async def change_directory(path: str) -> str:
        try:
            resolved = Shell._resolve_path(path)

            def _chdir() -> str:
                os.chdir(resolved)
                return os.getcwd()

            if pathlib.Path(resolved).is_file():
                logger.warning(
                    f"Provided path '{resolved}' is a file. Changing to its parent directory."
                )
                resolved = str(pathlib.Path(resolved).parent)

                def _chdir_parent() -> str:
                    os.chdir(resolved)
                    return os.getcwd()

                Shell.current_directory = await asyncio.to_thread(_chdir_parent)
                return f"Changed directory to {Shell.current_directory}"

            Shell.current_directory = await asyncio.to_thread(_chdir)
            return f"Changed directory to {Shell.current_directory}"
        except Exception as e:
            return f"Error changing directory: {str(e)}"

    @staticmethod
    def _resolve_directory(path: str | None = None) -> str:
        if not path:
            return Shell.current_directory
        return Shell._resolve_path(path)

    @staticmethod
    async def list_files(path: str | None = None) -> str:
        try:
            target_dir = Shell._resolve_directory(path)

            def _list() -> str:
                if not os.path.isdir(target_dir):
                    return f"Error listing files: '{path or target_dir}' is not a directory."
                files = os.listdir(target_dir)
                gitignore_path = os.path.join(target_dir, ".gitignore")
                if os.path.exists(gitignore_path):
                    with open(gitignore_path, "r") as gitignore_file:
                        ignored_files = [
                            line.strip() for line in gitignore_file if line.strip()
                        ]
                    files = [f for f in files if f not in ignored_files]
                files = [f for f in files if not f.startswith(".git")]
                files = [f for f in files if "node_modules" not in f]
                return "\n".join(files)

            return await asyncio.to_thread(_list)
        except Exception as e:
            return f"Error listing files: {str(e)}"

    @staticmethod
    async def get_directory_tree(
        path: str | None = None, max_depth: int = 3
    ) -> str:
        try:
            base_dir = Shell._resolve_directory(path)
            skip_names = Shell._walk_skip_names()

            def _tree() -> str:
                if not os.path.isdir(base_dir):
                    return (
                        f"Error generating directory tree: "
                        f"'{path or base_dir}' is not a directory."
                    )
                tree = []
                for root, dirs, files in os.walk(base_dir):
                    rel = os.path.relpath(root, base_dir)
                    level = 0 if rel == "." else rel.count(os.sep) + 1
                    if level > max_depth:
                        dirs[:] = []
                        continue
                    dirs[:] = [d for d in dirs if d not in skip_names and not d.startswith(".")]
                    indent = " " * 4 * level
                    label = os.path.basename(root) if rel != "." else os.path.basename(base_dir)
                    tree.append(f"{indent}{label}{os.path.sep}")
                    subindent = " " * 4 * (level + 1)
                    for f in files[:40]:
                        if f.startswith("."):
                            continue
                        tree.append(f"{subindent}{f}")
                    if len(files) > 40:
                        tree.append(f"{subindent}... ({len(files) - 40} more files)")
                return "\n".join(tree)

            return await asyncio.to_thread(_tree)
        except Exception as e:
            return f"Error generating directory tree: {str(e)}"

    @staticmethod
    def _detect_newline(content: str) -> str:
        if "\r\n" in content:
            return "\r\n"
        if "\r" in content:
            return "\r"
        return "\n"

    @staticmethod
    def _to_lf(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _from_lf(text: str, newline: str) -> str:
        if newline == "\n":
            return text
        return text.replace("\n", newline)

    @staticmethod
    async def read_file(filename: str, line: int = None) -> str:
        try:
            file_path = Shell._resolve_path(filename)

            def _read() -> str:
                with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                    if line is not None:
                        lines = file.readlines()
                        if 0 <= line - 1 < len(lines):
                            return lines[line - 1]
                        return ""
                    return file.read()

            return await asyncio.to_thread(_read)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @staticmethod
    async def sed(
        filename: str, old_string: str, new_string: str, line: int = None
    ) -> str:
        try:
            file_path = Shell._resolve_path(filename)

            def _sed() -> str:
                with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as file:
                    content = file.read()

                newline = Shell._detect_newline(content)
                content_lf = Shell._to_lf(content)
                old_lf = Shell._to_lf(old_string)
                new_lf = Shell._to_lf(new_string)

                if not old_lf:
                    return "EDIT_FAILED: old_string is empty."

                if line is not None:
                    lines = content_lf.splitlines(keepends=True)
                    if not (0 <= line - 1 < len(lines)):
                        return (
                            f"EDIT_FAILED: line {line} is out of range in {file_path} "
                            f"(file has {len(lines)} lines). Read the file first."
                        )
                    line_text = lines[line - 1]
                    if old_lf not in Shell._to_lf(line_text):
                        return (
                            f"EDIT_FAILED: old_string not found on line {line} of {file_path}. "
                            f"Read the file and copy the exact text from that line."
                        )
                    lines[line - 1] = line_text.replace(old_lf, new_lf, 1)
                    updated_lf = "".join(lines)
                    replacements = 1
                else:
                    occurrences = content_lf.count(old_lf)
                    if occurrences == 0:
                        return (
                            f"EDIT_FAILED: old_string not found in {file_path}. "
                            "Read the file and copy the exact text to replace. "
                            "Tip: include surrounding lines for uniqueness, and use one "
                            "sed call per change location."
                        )
                    if occurrences > 1:
                        return (
                            f"EDIT_FAILED: old_string appears {occurrences} times in {file_path}. "
                            "Use the `line` parameter or include more surrounding context "
                            "so old_string matches exactly once. "
                            "For two separate inserts, call sed/insert_after twice."
                        )
                    updated_lf = content_lf.replace(old_lf, new_lf, 1)
                    replacements = 1

                updated = Shell._from_lf(updated_lf, newline)
                with open(file_path, "w", encoding="utf-8", newline="") as file:
                    file.write(updated)
                return (
                    f"SUCCESS: replaced {replacements} occurrence(s) in {file_path}. "
                    "Re-read the file to verify if needed."
                )

            return await asyncio.to_thread(_sed)
        except Exception as e:
            return f"Error performing sed operation: {str(e)}"

    @staticmethod
    async def search_replace(
        filename: str, old_string: str, new_string: str, line: int = None
    ) -> str:
        """Preferred patch-style edit: replace one unique occurrence of old_string."""
        return await Shell.sed(
            filename=filename,
            old_string=old_string,
            new_string=new_string,
            line=line,
        )

    @staticmethod
    async def insert_after(
        filename: str, marker: str, content: str, line: int = None
    ) -> str:
        """Insert content immediately after a unique marker string (or a specific line)."""
        try:
            file_path = Shell._resolve_path(filename)

            def _insert() -> str:
                with open(
                    file_path, "r", encoding="utf-8", errors="replace", newline=""
                ) as file:
                    original = file.read()

                newline = Shell._detect_newline(original)
                original_lf = Shell._to_lf(original)
                # Trailing newlines on the marker would shift the insert one line too far
                # when combined with EOL handling / a line hint from the model.
                marker_lf = Shell._to_lf(marker or "").rstrip("\n")
                insert_lf = Shell._to_lf(content or "").rstrip("\n")

                if not insert_lf:
                    return "EDIT_FAILED: content is empty."

                insert_lf = insert_lf + "\n"

                def _insert_after_index(end: int) -> str:
                    """Insert after the line that ends at/after end-of-marker position."""
                    # If marker sits just before its line's newline, insert after that newline.
                    if end < len(original_lf) and original_lf[end] == "\n":
                        at = end + 1
                        return original_lf[:at] + insert_lf + original_lf[at:]
                    # Mid-line match: break onto the next line after the marker text.
                    return original_lf[:end] + "\n" + insert_lf + original_lf[end:]

                # Prefer marker when present — models often also pass `line` as the
                # destination line number (off-by-one / too late).
                if marker_lf:
                    matches = []
                    start = 0
                    while True:
                        idx = original_lf.find(marker_lf, start)
                        if idx < 0:
                            break
                        matches.append(idx)
                        start = idx + len(marker_lf)

                    if not matches:
                        return (
                            f"EDIT_FAILED: marker not found in {file_path}. "
                            "Copy the exact text to insert after."
                        )

                    if len(matches) == 1:
                        idx = matches[0]
                    elif line is not None:
                        # Disambiguate: pick the match that lies on this 1-based line.
                        lines = original_lf.splitlines(keepends=True)
                        if not (1 <= line <= len(lines)):
                            return (
                                f"EDIT_FAILED: line {line} is out of range in {file_path} "
                                f"(file has {len(lines)} lines)."
                            )
                        # Character offset of the start of that line.
                        line_start = sum(len(lines[i]) for i in range(line - 1))
                        line_end = line_start + len(lines[line - 1])
                        on_line = [m for m in matches if line_start <= m < line_end]
                        if not on_line:
                            return (
                                f"EDIT_FAILED: marker not found on line {line} of {file_path}."
                            )
                        idx = on_line[0]
                    else:
                        return (
                            f"EDIT_FAILED: marker appears {len(matches)} times in {file_path}. "
                            "Pass `line` (1-based line containing the marker) or include more "
                            "surrounding context. For two different inserts, call insert_after twice."
                        )

                    updated_lf = _insert_after_index(idx + len(marker_lf))
                elif line is not None:
                    lines = original_lf.splitlines(keepends=True)
                    if not (1 <= line <= len(lines)):
                        return (
                            f"EDIT_FAILED: line {line} is out of range in {file_path} "
                            f"(file has {len(lines)} lines)."
                        )
                    # Insert immediately after this 1-based line (before the following line).
                    lines.insert(line, insert_lf)
                    updated_lf = "".join(lines)
                else:
                    return "EDIT_FAILED: provide a marker string (preferred) or a line number."

                updated = Shell._from_lf(updated_lf, newline)
                with open(file_path, "w", encoding="utf-8", newline="") as file:
                    file.write(updated)
                return f"SUCCESS: inserted content after marker in {file_path}."

            return await asyncio.to_thread(_insert)
        except Exception as e:
            return f"Error inserting into file: {str(e)}"

    @staticmethod
    async def write_file(filename: str, content: str) -> str:
        try:
            file_path = Shell._resolve_path(filename)

            def _write() -> None:
                parent = os.path.dirname(file_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(file_path, "w", encoding="utf-8", newline="") as file:
                    file.write(content)

            await asyncio.to_thread(_write)
            return f"Wrote content to {file_path}"
        except Exception as e:
            return f"Error writing to file: {str(e)}"
