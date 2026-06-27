from core.tools.shell import Shell

class PythonTools:
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