import asyncio
import os


class Shell:
    current_directory = os.getcwd()

    @staticmethod
    async def find_files(pattern: str) -> str:
        try:
            def _find() -> str:
                matches = []
                for root, dirs, files in os.walk(Shell.current_directory):
                    for filename in files:
                        if pattern in filename:
                            matches.append(os.path.join(root, filename))
                return "\n".join(matches)

            return await asyncio.to_thread(_find)
        except Exception as e:
            return f"Error finding files: {str(e)}"

    @staticmethod
    async def search_text_in_files(pattern: str) -> str:
        try:
            def _search() -> str:
                matches = []
                for root, dirs, files in os.walk(Shell.current_directory):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        with open(file_path, "r", errors="ignore") as file:
                            for line_number, line in enumerate(file, start=1):
                                if pattern in line:
                                    matches.append(
                                        f"{file_path}:{line_number}: {line.strip()}"
                                    )
                return "\n".join(matches)

            return await asyncio.to_thread(_search)
        except Exception as e:
            return f"Error searching text in files: {str(e)}"

    @staticmethod
    async def mkdir(path: str) -> str:
        try:
            await asyncio.to_thread(
                os.makedirs, os.path.join(Shell.current_directory, path), exist_ok=True
            )
            return f"Directory '{path}' created successfully."
        except Exception as e:
            return f"Error creating directory: {str(e)}"

    @staticmethod
    async def delete_file(filename: str) -> str:
        try:
            await asyncio.to_thread(
                os.remove, os.path.join(Shell.current_directory, filename)
            )
            return f"File '{filename}' deleted successfully."
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    @staticmethod
    async def move_file(src: str, dest: str) -> str:
        try:
            await asyncio.to_thread(
                os.rename,
                os.path.join(Shell.current_directory, src),
                os.path.join(Shell.current_directory, dest),
            )
            return f"File '{src}' moved to '{dest}' successfully."
        except Exception as e:
            return f"Error moving file: {str(e)}"

    @staticmethod
    async def copy_file(src: str, dest: str) -> str:
        try:
            import shutil

            await asyncio.to_thread(
                shutil.copy,
                os.path.join(Shell.current_directory, src),
                os.path.join(Shell.current_directory, dest),
            )
            return f"File '{src}' copied to '{dest}' successfully."
        except Exception as e:
            return f"Error copying file: {str(e)}"

    @staticmethod
    async def move_file_to_directory(src: str, dest_dir: str) -> str:
        try:
            await asyncio.to_thread(
                os.makedirs,
                os.path.join(Shell.current_directory, dest_dir),
                exist_ok=True,
            )
            await asyncio.to_thread(
                os.rename,
                os.path.join(Shell.current_directory, src),
                os.path.join(Shell.current_directory, dest_dir, src),
            )
            return f"File '{src}' moved to directory '{dest_dir}' successfully."
        except Exception as e:
            return f"Error moving file to directory: {str(e)}"

    @staticmethod
    async def append_to_file(filename: str, content: str) -> str:
        try:
            def _append() -> None:
                with open(os.path.join(Shell.current_directory, filename), "a") as file:
                    file.write(content)

            await asyncio.to_thread(_append)
            return f"Appended content to {filename}"
        except Exception as e:
            return f"Error appending to file: {str(e)}"

    @staticmethod
    async def run_shell_command(command: str) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Shell.current_directory,
            )
            stdout, stderr = await process.communicate()
            stdout_text = stdout.decode(errors="ignore") if stdout else ""
            stderr_text = stderr.decode(errors="ignore") if stderr else ""

            if process.returncode == 0:
                return stdout_text
            return f"Error executing command: {stderr_text}"
        except Exception as e:
            return f"Error executing shell command: {str(e)}"

    @staticmethod
    async def change_directory(path: str) -> str:
        try:
            def _chdir() -> str:
                os.chdir(path)
                return os.getcwd()

            Shell.current_directory = await asyncio.to_thread(_chdir)
            return f"Changed directory to {Shell.current_directory}"
        except Exception as e:
            return f"Error changing directory: {str(e)}"

    @staticmethod
    async def list_files() -> str:
        try:
            def _list() -> str:
                files = os.listdir(Shell.current_directory)
                gitignore_path = os.path.join(Shell.current_directory, ".gitignore")
                if os.path.exists(gitignore_path):
                    with open(gitignore_path, "r") as gitignore_file:
                        ignored_files = [
                            line.strip() for line in gitignore_file if line.strip()
                        ]
                    files = [f for f in files if f not in ignored_files]
                files = [f for f in files if not f.startswith(".git")]
                return "\n".join(files)

            return await asyncio.to_thread(_list)
        except Exception as e:
            return f"Error listing files: {str(e)}"

    @staticmethod
    async def get_directory_tree() -> str:
        try:
            def _tree() -> str:
                tree = []
                for root, dirs, files in os.walk(Shell.current_directory):
                    level = root.replace(Shell.current_directory, "").count(os.sep)
                    indent = " " * 4 * level
                    tree.append(f"{indent}{os.path.basename(root)}/")
                    subindent = " " * 4 * (level + 1)
                    for f in files:
                        tree.append(f"{subindent}{f}")
                return "\n".join(tree)

            return await asyncio.to_thread(_tree)
        except Exception as e:
            return f"Error generating directory tree: {str(e)}"

    @staticmethod
    async def read_file(filename: str) -> str:
        try:
            def _read() -> str:
                with open(os.path.join(Shell.current_directory, filename), "r") as file:
                    return file.read()

            return await asyncio.to_thread(_read)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @staticmethod
    async def sed(filename: str, old_string: str, new_string: str, line: int = None) -> str:
        try:
            def _sed() -> None:
                file_path = os.path.join(Shell.current_directory, filename)
                with open(file_path, "r") as file:
                    content = file.read()
                if line is not None:
                    lines = content.split("\n")
                    if 0 <= line - 1 < len(lines):
                        lines[line - 1] = lines[line - 1].replace(old_string, new_string)
                    content = "\n".join(lines)
                else:
                    content = content.replace(old_string, new_string)
                with open(file_path, "w") as file:
                    file.write(content)

            await asyncio.to_thread(_sed)
            return f"Replaced '{old_string}' with '{new_string}' in {filename}"
        except Exception as e:
            return f"Error performing sed operation: {str(e)}"

    @staticmethod
    async def write_file(filename: str, content: str) -> str:
        try:
            def _write() -> None:
                with open(os.path.join(Shell.current_directory, filename), "w") as file:
                    file.write(content)

            await asyncio.to_thread(_write)
            return f"Wrote content to {filename}"
        except Exception as e:
            return f"Error writing to file: {str(e)}"
