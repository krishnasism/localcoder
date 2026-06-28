from core.tools.shell import Shell
import asyncio


class PythonTools:
    async def setup_python_virtual_env(self, env_name: str) -> str:
        try:
            venv_prefix = "agent_venv_"
            await Shell.run_shell_command(f"python -m venv {venv_prefix}{env_name}")
            windows = (
                await Shell.run_shell_command("echo %OS%")
            ).strip() == "Windows_NT"
            if windows:
                pip_cmd = f"{venv_prefix}{env_name}\\Scripts\\python -m pip"
            else:
                pip_cmd = f"{venv_prefix}{env_name}/bin/python -m pip"

            await Shell.run_shell_command(f"{pip_cmd} install --upgrade pip")
            await Shell.run_shell_command(f"{pip_cmd} install pytest pytest-cov")
            await Shell.run_shell_command(f"{pip_cmd} install -r requirements.txt")

            return (
                f"Virtual environment '{venv_prefix}{env_name}' created successfully."
            )
        except Exception as e:
            return f"Error creating virtual environment: {str(e)}"

    async def run_pytest(self, test_file_or_folder: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                test_file_or_folder,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Shell.current_directory,
            )
            stdout, stderr = await process.communicate()
            return (stdout.decode(errors="ignore") if stdout else "") + (
                stderr.decode(errors="ignore") if stderr else ""
            )
        except Exception as e:
            return f"Error running pytest: {str(e)}"

    async def run_pytest_with_coverage(self, test_file_or_folder: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                "--cov",
                ".",
                test_file_or_folder,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Shell.current_directory,
            )
            stdout, stderr = await process.communicate()
            return (stdout.decode(errors="ignore") if stdout else "") + (
                stderr.decode(errors="ignore") if stderr else ""
            )
        except Exception as e:
            return f"Error running pytest with coverage: {str(e)}"
