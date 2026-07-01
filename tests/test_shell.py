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


class TestShellNonFileOperations:
    """Tests for Shell static methods not covered by TestShellFileOperations."""

    def _chdir_to_temp(self):
        td = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(td)
        Shell.current_directory = td
        return td, original_dir

    def _restore(self, original_dir):
        os.chdir(original_dir)
        Shell.current_directory = os.path.dirname(os.path.abspath(__file__))

    # -- find_files --

    def test_find_files_matching(self):
        """find_files should match files containing the pattern."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("hello_world.txt", "content"))
            asyncio.run(Shell.write_file("world_hello.txt", "other"))
            result = asyncio.run(Shell.find_files("hello"))
            assert "hello_world.txt" in result
            assert "world_hello.txt" in result
        finally:
            self._restore(original_dir)

    def test_find_files_no_match(self):
        """find_files with no match returns empty string."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("abc.txt", "content"))
            result = asyncio.run(Shell.find_files("xyz"))
            assert result == ""
        finally:
            self._restore(original_dir)

    # -- search_text_in_files --

    def test_search_text_in_files_matching(self):
        """search_text should find lines containing the pattern."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("data.txt", "hello world"))
            result = asyncio.run(Shell.search_text_in_files("hello"))
            assert "data.txt" in result
            assert "hello world" in result
        finally:
            self._restore(original_dir)

    def test_search_text_in_files_not_found(self):
        """search_text with no match returns empty string."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("data.txt", "hello world"))
            result = asyncio.run(Shell.search_text_in_files("nonexistent"))
            assert result == ""
        finally:
            self._restore(original_dir)

    def test_search_text_in_files_error(self):
        """search_text_in_files should return an error message on exception."""
        import unittest.mock as mock

        td, original_dir = self._chdir_to_temp()
        try:

            async def _fail(*args, **kwargs):
                raise OSError("walk failed")

            with mock.patch.object(asyncio, "to_thread", side_effect=_fail):
                result = asyncio.run(Shell.search_text_in_files("anything"))
                assert "Error searching text in files" in result
        finally:
            self._restore(original_dir)

    # -- run_shell_command --

    def test_run_shell_command_success_win(self):
        """run_shell_command should succeed on Windows echo command."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.run_shell_command("echo hello"))
            assert (
                "hello" in result
            )  # output may or may not include trailing whitespace
        finally:
            self._restore(original_dir)

    def test_run_shell_command_failure(self):
        """run_shell_command should return error message for failing command."""
        td, original_dir = self._chdir_to_temp()
        try:
            if os.name == "nt":
                invalid_cmd = "nonexistentcommand_that_does_not_exist_abc123"
            else:
                invalid_cmd = "ls /nonexistent/path_xyz"
            result = asyncio.run(Shell.run_shell_command(invalid_cmd))
            assert result.startswith("Error")
        finally:
            self._restore(original_dir)

    def test_run_shell_command_exception(self):
        """run_shell_command should catch exceptions and return error message."""
        td, original_dir = self._chdir_to_temp()
        try:
            # Patch to simulate an exception during subprocess creation
            import unittest.mock as mock

            async def _fail(*args, **kwargs):
                raise RuntimeError("subprocess failure")

            with mock.patch.object(
                asyncio, "create_subprocess_shell", side_effect=_fail
            ):
                result = asyncio.run(Shell.run_shell_command("fake"))
                assert "Error executing shell command" in result
        finally:
            self._restore(original_dir)

    # -- change_directory --

    def test_change_directory_success(self):
        """change_directory should update the current path on success."""
        td, original_dir = self._chdir_to_temp()
        try:
            subdir = os.path.join(td, "new_subdir")
            os.makedirs(subdir)
            asyncio.run(Shell.change_directory(subdir))
            assert Shell.current_directory == subdir
        finally:
            self._restore(original_dir)

    def test_change_directory_error(self):
        """change_directory should return an error for non-existent directory."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.change_directory("/nonexistent/path_xyz"))
            assert "Error changing directory" in result
        finally:
            self._restore(original_dir)

    # -- list_files --

    def test_list_files(self):
        """list_files should return filenames, excluding .git files."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("visible.txt", "data"))
            result = asyncio.run(Shell.list_files())
            assert "visible.txt" in result
        finally:
            self._restore(original_dir)

    def test_list_files_with_gitignore(self):
        """list_files should honour .gitignore entries."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file(".gitignore", "ignored_file.txt\n"))
            asyncio.run(Shell.write_file("ignored_file.txt", "content"))
            asyncio.run(Shell.write_file("visible.txt", "data"))
            result = asyncio.run(Shell.list_files())
            assert "visible.txt" in result
            assert "ignored_file.txt" not in result
        finally:
            self._restore(original_dir)

    # -- get_directory_tree --

    def test_get_directory_tree(self):
        """get_directory_tree should produce non-empty tree output."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("root.txt", "data"))
            asyncio.run(Shell.mkdir("subdir"))
            asyncio.run(Shell.write_file(os.path.join("subdir", "inner.txt"), "data"))
            result = asyncio.run(Shell.get_directory_tree())
            assert "root.txt" in result
            assert "subdir" in result
        finally:
            self._restore(original_dir)

    # -- sed (line parameter) --

    def test_sed_with_line(self):
        """sed with line number should only modify that specific line."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("multi.txt", "first\nsecond\nthird\n"))
            result = asyncio.run(Shell.sed("multi.txt", "second", "SECOND", line=2))
            assert "SUCCESS" in result
            content = asyncio.run(Shell.read_file("multi.txt"))
            lines = content.split("\n")
            assert lines[1] == "SECOND"
            assert lines[0] == "first"
            assert lines[2] == "third"
        finally:
            self._restore(original_dir)

    def test_sed_without_line(self):
        """sed without line should replace a single unique occurrence."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("all.txt", "aa\nbb\ncc\n"))
            result = asyncio.run(Shell.sed("all.txt", "bb", "ZZ"))
            assert "SUCCESS" in result
            content = asyncio.run(Shell.read_file("all.txt"))
            assert "bb" not in content
            assert "ZZ" in content
            assert content.count("ZZ") == 1
        finally:
            self._restore(original_dir)

    def test_sed_rejects_ambiguous_match(self):
        """sed without line should fail when old_string appears multiple times."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("all.txt", "aa\nbb\naa\n"))
            result = asyncio.run(Shell.sed("all.txt", "aa", "ZZ"))
            assert result.startswith("EDIT_FAILED:")
            content = asyncio.run(Shell.read_file("all.txt"))
            assert content == "aa\nbb\naa\n"
        finally:
            self._restore(original_dir)

    def test_sed_rejects_missing_match(self):
        """sed should fail clearly when old_string is not in the file."""
        td, original_dir = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("all.txt", "hello\n"))
            result = asyncio.run(Shell.sed("all.txt", "missing", "ZZ"))
            assert result.startswith("EDIT_FAILED:")
        finally:
            self._restore(original_dir)

    # -- error paths for existing methods --

    def test_write_file_error(self):
        """write_file should return an error message on exception."""
        import unittest.mock as mock

        td, original_dir = self._chdir_to_temp()
        try:

            async def _fail(*args, **kwargs):
                raise OSError("write failed")

            with mock.patch.object(asyncio, "to_thread", side_effect=_fail):
                result = asyncio.run(Shell.write_file("x.txt", "c"))
                assert "Error writing to file" in result
        finally:
            self._restore(original_dir)

    def test_read_file_error(self):
        """read_file should return an error message for non-existent file."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.read_file("nonexistent.txt"))
            assert "Error reading file" in result
        finally:
            self._restore(original_dir)

    def test_read_file_line_error(self):
        """read_file should return an error message for non-existent file."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.read_file("nonexistent.txt", line=1))
            assert "Error reading file" in result
        finally:
            self._restore(original_dir)

    def test_delete_file_error(self):
        """delete_file should return an error for non-existent file."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.delete_file("no_such_file.txt"))
            assert "Error deleting file" in result
        finally:
            self._restore(original_dir)

    def test_copy_file_error(self):
        """copy_file should return an error for non-existent source."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.copy_file("ghost.txt", "target.txt"))
            assert "Error copying file" in result
        finally:
            self._restore(original_dir)

    def test_move_file_error(self):
        """move_file should return an error for non-existent source."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(Shell.move_file("ghost.txt", "target.txt"))
            assert "Error moving file" in result
        finally:
            self._restore(original_dir)

    def test_append_to_file_error(self):
        """append_to_file should return an error for non-existent file."""
        import unittest.mock as mock

        td, original_dir = self._chdir_to_temp()
        try:

            async def _fail(*args, **kwargs):
                raise OSError("append failed")

            with mock.patch.object(asyncio, "to_thread", side_effect=_fail):
                result = asyncio.run(Shell.append_to_file("nonexistent.txt", "data"))
                assert "Error appending to file" in result
        finally:
            self._restore(original_dir)

    def test_mkdir_error(self):
        """mkdir should return an error on failure."""
        import unittest.mock as mock

        td, original_dir = self._chdir_to_temp()
        try:

            async def _fail(*args, **kwargs):
                raise OSError("makedirs failed")

            with mock.patch.object(asyncio, "to_thread", side_effect=_fail):
                result = asyncio.run(Shell.mkdir("new_dir"))
                assert "Error creating directory" in result
        finally:
            self._restore(original_dir)

    def test_move_file_to_directory_success(self):
        """move_file_to_directory should move a file into a new directory."""
        td, original_dir = self._chdir_to_temp()
        try:
            filename = "source.txt"
            content = "move me to dir!"
            dest_dir = "target_dir"

            # Create the source file
            asyncio.run(Shell.write_file(filename, content))
            assert os.path.isfile(os.path.join(td, filename))

            # Move it to a new directory (dir should be auto-created)
            result = asyncio.run(Shell.move_file_to_directory(filename, dest_dir))
            assert (
                f"File '{filename}' moved to directory '{dest_dir}' successfully."
                == result
            )
            assert not os.path.exists(os.path.join(td, filename))  # original gone
            assert os.path.isdir(os.path.join(td, dest_dir))
            assert os.path.isfile(os.path.join(td, dest_dir, filename))

            # Verify content survived the move
            assert (
                asyncio.run(Shell.read_file(os.path.join(dest_dir, filename)))
                == content
            )
        finally:
            self._restore(original_dir)

    def test_move_file_to_directory_error(self):
        """move_file_to_directory should return an error for non-existent source."""
        td, original_dir = self._chdir_to_temp()
        try:
            result = asyncio.run(
                Shell.move_file_to_directory("ghost.txt", "target_dir")
            )
            assert "Error moving file to directory" in result
        finally:
            self._restore(original_dir)

    def test_read_file(self):
        """read_file should return the content of an existing file."""
        td, original_dir = self._chdir_to_temp()
        try:
            filename = "read_test.txt"
            content = "This is a test for read_file."
            asyncio.run(Shell.write_file(filename, content))
            result = asyncio.run(Shell.read_file(filename))
            assert result == content
        finally:
            self._restore(original_dir)

    def test_read_file_line(self):
        """read_file with line parameter should return the specific line."""
        td, original_dir = self._chdir_to_temp()
        try:
            filename = "line_test.txt"
            content = "first line\nsecond line\nthird line\n"
            asyncio.run(Shell.write_file(filename, content))
            result = asyncio.run(Shell.read_file(filename, line=2))
            assert result.strip().strip("\n") == "second line"
        finally:
            self._restore(original_dir)
