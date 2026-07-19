import asyncio
import os
import tempfile

from core.tools.patch import (
    apply_patch_text,
    apply_string_replace,
    parse_patch,
    replace_line_range,
)
from core.tools.shell import Shell


def test_parse_patch_multi_hunk():
    patch = """\
@@
 line1
-line2
+line2b
 line3
@@
 line5
-line6
+line6b
"""
    hunks = parse_patch(patch)
    assert len(hunks) == 2


def test_apply_single_hunk():
    content = "a\nb\nc\n"
    patch = "@@\n a\n-b\n+B\n c\n"
    updated, msg = apply_patch_text(content, patch)
    assert updated is not None
    assert "SUCCESS" in msg
    assert updated == "a\nB\nc\n"


def test_apply_multi_hunk_same_file():
    content = "one\ntwo\nthree\nfour\nfive\n"
    patch = """\
@@
 one
-two
+TWO
 three
@@
 four
-five
+FIVE
"""
    updated, msg = apply_patch_text(content, patch)
    assert updated is not None
    assert "2 hunk" in msg
    assert updated == "one\nTWO\nthree\nfour\nFIVE\n"


def test_apply_patch_whitespace_relaxed():
    content = "def foo():\n    return  1\n"
    # patch uses single space where file has double space
    patch = "@@\n def foo():\n-    return 1\n+    return 2\n"
    updated, msg = apply_patch_text(content, patch)
    assert updated is not None
    assert "SUCCESS" in msg
    assert "return 2" in updated


def test_apply_patch_abort_leaves_logic_unchanged():
    content = "a\nb\nc\n"
    patch = """\
@@
 a
-b
+B
@@
 x
-y
+z
"""
    updated, msg = apply_patch_text(content, patch)
    assert updated is None
    assert msg.startswith("EDIT_FAILED:")
    # original content argument unchanged (caller responsibility); engine returns None


def test_apply_patch_preserves_no_trailing_newline_when_absent():
    content = "a\nb"
    patch = "@@\n a\n-b\n+B\n"
    updated, msg = apply_patch_text(content, patch)
    assert updated is not None
    assert updated == "a\nB"


def test_replace_line_range():
    content = "1\n2\n3\n4\n"
    updated, msg = replace_line_range(content, 2, 3, "X\nY\n")
    assert updated == "1\nX\nY\n4\n"
    assert "SUCCESS" in msg


def test_search_replace_whitespace_relaxed():
    content = "hello   world\n"
    updated, msg = apply_string_replace(content, "hello world", "hello there")
    assert updated is not None
    assert "SUCCESS" in msg
    assert "hello there" in updated


def test_search_replace_ambiguous():
    content = "aa\nbb\naa\n"
    updated, msg = apply_string_replace(content, "aa", "zz")
    assert updated is None
    assert "appears 2 times" in msg or "matches 2" in msg


def test_search_replace_all():
    content = "aa\nbb\naa\n"
    updated, msg = apply_string_replace(content, "aa", "zz", replace_all=True)
    assert updated == "zz\nbb\nzz\n"
    assert "SUCCESS" in msg


class TestShellPatchWrappers:
    def _chdir_to_temp(self):
        td = tempfile.mkdtemp()
        original = os.getcwd()
        os.chdir(td)
        Shell.current_directory = td
        return td, original

    def _restore(self, original):
        os.chdir(original)
        Shell.current_directory = os.path.dirname(os.path.abspath(__file__))

    def test_apply_patch_crlf(self):
        td, original = self._chdir_to_temp()
        try:
            path = os.path.join(td, "f.txt")
            with open(path, "wb") as f:
                f.write(b"a\r\nb\r\nc\r\n")
            result = asyncio.run(
                Shell.apply_patch(
                    "@@\n a\n-b\n+B\n c\n",
                    filename="f.txt",
                )
            )
            assert "SUCCESS" in result
            with open(path, "rb") as f:
                data = f.read()
            assert b"\r\n" in data
            assert b"B" in data
            assert b"b\r\n" not in data or data.count(b"b") == 0
        finally:
            self._restore(original)

    def test_apply_patch_transactional_abort(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("f.txt", "a\nb\nc\n"))
            before = asyncio.run(Shell.read_file("f.txt"))
            result = asyncio.run(
                Shell.apply_patch(
                    "@@\n a\n-b\n+B\n c\n@@\n missing\n-x\n+y\n",
                    filename="f.txt",
                )
            )
            assert result.startswith("EDIT_FAILED:")
            after = asyncio.run(Shell.read_file("f.txt"))
            assert after == before
            assert "B" not in after or after == before
        finally:
            self._restore(original)

    def test_apply_patch_multi_file_and_add(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("a.txt", "hello\nworld\n"))
            patch = """\
*** Begin Patch
*** Update File: a.txt
@@
 hello
-world
+WORLD
*** Add File: b.txt
+new
+file
*** End Patch
"""
            result = asyncio.run(Shell.apply_patch(patch))
            assert "SUCCESS" in result
            assert asyncio.run(Shell.read_file("a.txt")) == "hello\nWORLD\n"
            assert asyncio.run(Shell.read_file("b.txt")) == "new\nfile\n"
        finally:
            self._restore(original)

    def test_apply_patch_dry_run(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("a.txt", "x\n"))
            result = asyncio.run(
                Shell.apply_patch(
                    "@@\n-x\n+y\n",
                    filename="a.txt",
                    dry_run=True,
                )
            )
            assert "SUCCESS" in result
            assert "dry_run" in result
            assert asyncio.run(Shell.read_file("a.txt")) == "x\n"
        finally:
            self._restore(original)

    def test_replace_lines_shell(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("f.txt", "a\nb\nc\n"))
            result = asyncio.run(Shell.replace_lines("f.txt", 2, 2, "B\n"))
            assert "SUCCESS" in result
            assert asyncio.run(Shell.read_file("f.txt")) == "a\nB\nc\n"
        finally:
            self._restore(original)

    def test_read_file_line_range(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("f.txt", "a\nb\nc\nd\n"))
            result = asyncio.run(Shell.read_file("f.txt", start_line=2, end_line=3))
            assert "lines 2-3" in result
            assert "b\n" in result
            assert "c\n" in result
        finally:
            self._restore(original)

    def test_search_replace_fuzzy(self):
        td, original = self._chdir_to_temp()
        try:
            asyncio.run(Shell.write_file("f.txt", "foo   bar\n"))
            result = asyncio.run(Shell.search_replace("f.txt", "foo bar", "foo baz"))
            assert "SUCCESS" in result
            assert "foo baz" in asyncio.run(Shell.read_file("f.txt"))
        finally:
            self._restore(original)
