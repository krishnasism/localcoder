from core.tools.shell import Shell


class PythonTools:
    def setup_python_virtual_env(self, env_name: str) -> str:
        try:
            Shell.run_shell_command(f"python -m venv {env_name}")
            windows = Shell.run_shell_command("echo %OS%").strip() == "Windows_NT"
            if windows:
                Shell.run_shell_command(f"{env_name}\\Scripts\\activate")
            else:
                Shell.run_shell_command(f"source {env_name}/bin/activate")
            Shell.run_shell_command("pip install --upgrade pip")
            Shell.run_shell_command("pip install pytest pytest-cov")
            Shell.run_shell_command("pip install -r requirements.txt")

            return f"Virtual environment '{env_name}' created successfully."
        except Exception as e:
            return f"Error creating virtual environment: {str(e)}"

    def run_pytest(self, test_file_or_folder: str) -> str:
        try:
            import subprocess

            result = subprocess.run(
                ["pytest", test_file_or_folder],
                capture_output=True,
                text=True,
                cwd=Shell.current_directory,
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error running pytest: {str(e)}"

    def run_pytest_with_coverage(self, test_file_or_folder: str) -> str:
        try:
            import subprocess

            result = subprocess.run(
                ["pytest", "--cov", ".", test_file_or_folder],
                capture_output=True,
                text=True,
                cwd=Shell.current_directory,
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error running pytest with coverage: {str(e)}"
