import os
import asyncio
import tempfile
from core.tools.shell import Shell


class TestShellFileOperations:
    """Tests for Shell static methods that operate on files in the current directory."""

    def _chdir_to_temp(self):
        """Helper: create a temp dir, change into it, and return its path."""
        td = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(td)
        Shell.current_directory = td
        return td, original_dir

    def _restore(self, original_dir):
        """Helper: restore the original working directory."""
        os.chdir(original_dir)
        Shell.current_directory = os.path.dirname(os.path.abspath(__file__))

    def test_create_and_delete_file_via_write_and_delete(self):
        filename = "test_unit_shell.txt"
        content = "Hello, unit testing!"

        td, original_dir = self._chdir_to_temp()
        try:
            # Write a file
            assert (
                asyncio.run(Shell.write_file(filename, content))
                == f"Wrote content to {filename}"
            )
            assert os.path.isfile(os.path.join(td, filename))

            # Read it back via read_file to verify content
            result = asyncio.run(Shell.read_file(filename))
            assert result == content

            # Delete the file
            assert (
                asyncio.run(Shell.delete_file(filename))
                == f"File '{filename}' deleted successfully."
            )
            assert not os.path.exists(os.path.join(td, filename))
        finally:
            self._restore(original_dir)

    def test_copy_and_move_file(self):
        src_name = "source_unit.txt"
        dest_name = "dest_unit.txt"
        content = "move me around!"

        td, original_dir = self._chdir_to_temp()
        try:
            # Create source file
            asyncio.run(Shell.write_file(src_name, content))
            assert os.path.isfile(os.path.join(td, src_name))

            # Copy
            assert (
                asyncio.run(Shell.copy_file(src_name, dest_name))
                == f"File '{src_name}' copied to '{dest_name}' successfully."
            )
            assert os.path.isfile(
                os.path.join(td, src_name)
            )  # source should still exist
            assert os.path.isfile(os.path.join(td, dest_name))

            # Move (rename) the copy
            moved_name = "moved_unit.txt"
            assert (
                asyncio.run(Shell.move_file(dest_name, moved_name))
                == f"File '{dest_name}' moved to '{moved_name}' successfully."
            )
            assert not os.path.exists(os.path.join(td, dest_name))  # original copy gone
            assert os.path.isfile(os.path.join(td, moved_name))

            # Verify content survived the round-trip
            assert asyncio.run(Shell.read_file(moved_name)) == content
        finally:
            self._restore(original_dir)

    def test_append_to_file(self):
        filename = "append_test.txt"
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file(filename, "line_one\n"))
            assert (
                asyncio.run(Shell.append_to_file(filename, "line_two\n"))
                == f"Appended content to {filename}"
            )
            result = asyncio.run(Shell.read_file(filename))
            assert result == "line_one\nline_two\n"
        finally:
            self._restore(original_dir)

    def test_mkdir_and_file_in_subdir(self):
        dirname = "nested_test_dir"
        td, original_dir = self._chdir_to_temp()
        try:
            assert (
                asyncio.run(Shell.mkdir(dirname))
                == f"Directory '{dirname}' created successfully."
            )
            assert os.path.isdir(os.path.join(td, dirname))

            # Create a file inside the subdir and read it via Shell
            shell_path = os.path.join(dirname, "inner.txt")
            asyncio.run(Shell.write_file(shell_path, "inside nested dir"))
            result = asyncio.run(Shell.read_file(shell_path))
            assert result == "inside nested dir"
        finally:
            self._restore(original_dir)
