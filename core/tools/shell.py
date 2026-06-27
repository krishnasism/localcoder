import os


class Shell:
    current_directory = os.getcwd()

    @staticmethod
    def change_directory(path: str) -> str:
        try:
            os.chdir(path)
            Shell.current_directory = os.getcwd()
            return f"Changed directory to {Shell.current_directory}"
        except Exception as e:
            return f"Error changing directory: {str(e)}"

    @staticmethod
    def list_files() -> str:
        try:
            files = os.listdir(Shell.current_directory)
            return "\n".join(files)
        except Exception as e:
            return f"Error listing files: {str(e)}"

    @staticmethod
    def get_directory_tree() -> str:
        try:
            tree = []
            for root, dirs, files in os.walk(Shell.current_directory):
                level = root.replace(Shell.current_directory, "").count(os.sep)
                indent = " " * 4 * level
                tree.append(f"{indent}{os.path.basename(root)}/")
                subindent = " " * 4 * (level + 1)
                for f in files:
                    tree.append(f"{subindent}{f}")
            return "\n".join(tree)
        except Exception as e:
            return f"Error generating directory tree: {str(e)}"

    @staticmethod
    def read_file(filename: str) -> str:
        try:
            with open(os.path.join(Shell.current_directory, filename), "r") as file:
                return file.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @staticmethod
    def sed(filename: str, old_string: str, new_string: str, line: int = None) -> str:
        try:
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
            return f"Replaced '{old_string}' with '{new_string}' in {filename}"
        except Exception as e:
            return f"Error performing sed operation: {str(e)}"

    @staticmethod
    def write_file(filename: str, content: str) -> str:
        try:
            with open(os.path.join(Shell.current_directory, filename), "w") as file:
                file.write(content)
            return f"Wrote content to {filename}"
        except Exception as e:
            return f"Error writing to file: {str(e)}"
