"""Unified-diff style patch parse/apply for agent file edits."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class HunkLine:
    kind: str  # " ", "-", "+"
    text: str  # without trailing newline


@dataclass
class Hunk:
    lines: list[HunkLine] = field(default_factory=list)
    header: str = ""


@dataclass
class FilePatch:
    """One file operation inside a multi-file patch."""

    path: str
    action: str  # "update" | "add"
    hunks: list[Hunk] = field(default_factory=list)
    add_lines: list[str] = field(default_factory=list)  # for action=add


MAX_PATCH_CHARS = 100_000
MAX_HUNKS_PER_PATCH = 40
MAX_FILES_PER_PATCH = 12


_HUNK_HEADER = re.compile(r"^@@")


def normalize_ws_line(line: str) -> str:
    """Collapse internal whitespace runs; keep leading indent structure lightly."""
    # Preserve leading whitespace length loosely by normalizing only trailing + internal.
    stripped_trail = line.rstrip()
    if not stripped_trail:
        return ""
    leading = len(stripped_trail) - len(stripped_trail.lstrip(" \t"))
    body = stripped_trail[leading:]
    body = re.sub(r"[ \t]+", " ", body)
    return (" " * leading) + body


def lines_equal_exact(a: str, b: str) -> bool:
    return a == b


def lines_equal_relaxed(a: str, b: str) -> bool:
    return normalize_ws_line(a) == normalize_ws_line(b)


def parse_patch(patch: str) -> list[Hunk]:
    """
    Parse a simplified unified diff into hunks (single-file body, no file headers).

    Accepts:
    - Full unified diffs with @@ headers
    - Bare hunks of ' ', '-', '+' lines
    - Optional *** Begin/End Patch wrappers (ignored)
    - *** Update/Add File headers are skipped (use parse_file_patches for those)
    """
    sections = parse_file_patches(patch)
    if len(sections) == 1 and sections[0].action == "update" and not sections[0].path:
        return sections[0].hunks
    if len(sections) == 1 and sections[0].action == "update":
        return sections[0].hunks
    # Multi-file or add: return all update hunks flattened (legacy helper).
    hunks: list[Hunk] = []
    for section in sections:
        hunks.extend(section.hunks)
    return hunks


def parse_file_patches(patch: str) -> list[FilePatch]:
    """Parse Codex-style multi-file patches or a bare single-file hunk body."""
    if not patch or not patch.strip():
        return []

    text = patch.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > MAX_PATCH_CHARS:
        raise ValueError(
            f"EDIT_FAILED: patch too large ({len(text)} chars; max {MAX_PATCH_CHARS})."
        )

    raw_lines = text.split("\n")
    while raw_lines and raw_lines[-1] == "":
        raw_lines.pop()

    sections: list[FilePatch] = []
    current_file: FilePatch | None = None
    current_hunk: Hunk | None = None
    in_add = False

    def _flush_hunk() -> None:
        nonlocal current_hunk
        if current_file is not None and current_hunk is not None and current_hunk.lines:
            current_file.hunks.append(current_hunk)
        current_hunk = None

    def _flush_file() -> None:
        nonlocal current_file, in_add
        _flush_hunk()
        if current_file is not None:
            if (
                current_file.action == "add"
                or current_file.hunks
                or current_file.add_lines
            ):
                sections.append(current_file)
        current_file = None
        in_add = False

    def _ensure_file() -> FilePatch:
        nonlocal current_file
        if current_file is None:
            current_file = FilePatch(path="", action="update")
        return current_file

    for raw in raw_lines:
        if raw.startswith("*** Begin Patch") or raw.startswith("*** End Patch"):
            continue
        if raw.startswith("*** Update File:"):
            _flush_file()
            path = raw.split(":", 1)[1].strip()
            current_file = FilePatch(path=path, action="update")
            in_add = False
            continue
        if raw.startswith("*** Add File:"):
            _flush_file()
            path = raw.split(":", 1)[1].strip()
            current_file = FilePatch(path=path, action="add")
            in_add = True
            continue
        if raw.startswith("*** Delete File:"):
            _flush_file()
            # v1: reject delete to keep scope small
            path = raw.split(":", 1)[1].strip()
            raise ValueError(
                f"EDIT_FAILED: Delete File not supported yet ({path}). "
                "Use delete_file tool instead."
            )
        if raw.startswith("--- ") or raw.startswith("+++ "):
            continue
        if _HUNK_HEADER.match(raw):
            in_add = False
            _flush_hunk()
            _ensure_file()
            current_hunk = Hunk(header=raw)
            continue

        if in_add and current_file is not None and current_file.action == "add":
            if raw.startswith("+"):
                current_file.add_lines.append(raw[1:])
            elif raw.startswith(" "):
                current_file.add_lines.append(raw[1:])
            elif raw.startswith("-"):
                continue
            else:
                current_file.add_lines.append(raw)
            continue

        if not raw and current_hunk is None:
            continue

        if raw.startswith("\\"):
            continue

        kind = " "
        body = raw
        if raw.startswith("+") and not raw.startswith("+++"):
            kind = "+"
            body = raw[1:]
        elif raw.startswith("-") and not raw.startswith("---"):
            kind = "-"
            body = raw[1:]
        elif raw.startswith(" "):
            kind = " "
            body = raw[1:]
        elif current_hunk is not None:
            kind = " "
            body = raw
        else:
            _ensure_file()
            current_hunk = Hunk()
            kind = " "
            body = raw

        if current_hunk is None:
            _ensure_file()
            current_hunk = Hunk()
        current_hunk.lines.append(HunkLine(kind=kind, text=body))

    _flush_file()

    total_hunks = sum(len(s.hunks) for s in sections) + sum(
        1 for s in sections if s.action == "add"
    )
    if total_hunks > MAX_HUNKS_PER_PATCH:
        raise ValueError(
            f"EDIT_FAILED: too many hunks ({total_hunks}; max {MAX_HUNKS_PER_PATCH})."
        )
    if len(sections) > MAX_FILES_PER_PATCH:
        raise ValueError(
            f"EDIT_FAILED: too many files ({len(sections)}; max {MAX_FILES_PER_PATCH})."
        )
    return sections


def apply_patch_text(content: str, patch: str) -> tuple[str | None, str]:
    """Parse a single-file patch body and apply to content."""
    try:
        sections = parse_file_patches(patch)
    except ValueError as exc:
        return None, str(exc)
    if not sections:
        return None, "EDIT_FAILED: patch contained no hunks."
    if len(sections) > 1 or (sections[0].path and sections[0].action == "add"):
        return (
            None,
            "EDIT_FAILED: multi-file / Add File patches require apply_patch without "
            "pre-bound content; use Shell.apply_patch with file headers in the patch.",
        )
    return apply_hunks_to_text(content, sections[0].hunks)


def _snippet(file_lines: list[str], center: int, radius: int = 3) -> str:
    start = max(0, center - radius)
    end = min(len(file_lines), center + radius + 1)
    parts = []
    for i in range(start, end):
        parts.append(f"{i + 1:>4}|{file_lines[i]}")
    return "\n".join(parts)


def _find_block(
    file_lines: list[str],
    old_lines: list[str],
    *,
    start_at: int = 0,
    relaxed: bool = False,
) -> list[int]:
    """Return start indices where old_lines matches file_lines."""
    if not old_lines:
        return [start_at] if start_at <= len(file_lines) else []

    eq = lines_equal_relaxed if relaxed else lines_equal_exact
    matches: list[int] = []
    max_start = len(file_lines) - len(old_lines)
    for i in range(start_at, max_start + 1):
        ok = True
        for j, old in enumerate(old_lines):
            if not eq(file_lines[i + j], old):
                ok = False
                break
        if ok:
            matches.append(i)
    return matches


def apply_hunks_to_text(content_lf: str, hunks: list[Hunk]) -> tuple[str | None, str]:
    """
    Apply hunks transactionally to LF-normalized text.

    Returns (new_content, message). new_content is None on failure.
    """
    if not hunks:
        return None, "EDIT_FAILED: patch contained no hunks."

    file_lines = content_lf.splitlines()
    # Track whether original ended with newline.
    ends_with_nl = content_lf.endswith("\n")
    cursor = 0
    applied = 0

    for hunk_idx, hunk in enumerate(hunks, start=1):
        old_lines = [ln.text for ln in hunk.lines if ln.kind in {" ", "-"}]
        new_lines = [ln.text for ln in hunk.lines if ln.kind in {" ", "+"}]

        # Pure addition with no context: append at end if old_lines empty from only +.
        if not old_lines and new_lines:
            # Only '+' lines — insert at cursor (after last apply) or EOF.
            insert_at = cursor if cursor <= len(file_lines) else len(file_lines)
            file_lines[insert_at:insert_at] = new_lines
            cursor = insert_at + len(new_lines)
            applied += 1
            continue

        if not old_lines:
            return None, f"EDIT_FAILED: hunk {hunk_idx} is empty."

        matches = _find_block(file_lines, old_lines, start_at=0, relaxed=False)
        mode = "exact"
        if not matches:
            matches = _find_block(file_lines, old_lines, start_at=0, relaxed=True)
            mode = "whitespace-relaxed"

        if not matches:
            # Prefer searching near cursor for a hint snippet.
            hint_at = min(cursor, max(0, len(file_lines) - 1))
            return (
                None,
                (
                    f"EDIT_FAILED: hunk {hunk_idx} did not match file content "
                    f"(tried exact and whitespace-relaxed).\n"
                    f"Expected old block ({len(old_lines)} line(s)) starting like:\n"
                    + "\n".join(f"  |{line}" for line in old_lines[:6])
                    + (
                        f"\n  |... ({len(old_lines) - 6} more)"
                        if len(old_lines) > 6
                        else ""
                    )
                    + f"\nNearby file context around line {hint_at + 1}:\n"
                    + _snippet(file_lines, hint_at)
                    + "\nRetry with apply_patch using exact file text, or use replace_lines."
                ),
            )

        # Prefer match at/after cursor to apply sequentially.
        chosen = None
        for m in matches:
            if m >= cursor:
                chosen = m
                break
        if chosen is None:
            if len(matches) == 1:
                chosen = matches[0]
            else:
                locs = ", ".join(str(m + 1) for m in matches[:8])
                return (
                    None,
                    (
                        f"EDIT_FAILED: hunk {hunk_idx} matches {len(matches)} locations "
                        f"(lines {locs}). Add more context lines so the hunk is unique."
                    ),
                )

        if len([m for m in matches if m >= cursor]) > 1 and chosen is not None:
            # Multiple forward matches — require uniqueness among remaining.
            forward = [m for m in matches if m >= cursor]
            if len(forward) > 1:
                locs = ", ".join(str(m + 1) for m in forward[:8])
                return (
                    None,
                    (
                        f"EDIT_FAILED: hunk {hunk_idx} is ambiguous "
                        f"({len(forward)} matches at lines {locs}). "
                        "Add more surrounding context."
                    ),
                )

        file_lines[chosen : chosen + len(old_lines)] = new_lines
        cursor = chosen + len(new_lines)
        applied += 1
        _ = mode  # retained for potential logging

    result = "\n".join(file_lines)
    if ends_with_nl and (result and not result.endswith("\n")):
        result += "\n"
    elif (
        not ends_with_nl
        and result.endswith("\n")
        and content_lf
        and not content_lf.endswith("\n")
    ):
        result = result[:-1]

    return (
        result,
        f"SUCCESS: applied {applied} hunk(s), {len(file_lines)} lines in result.",
    )


def plan_filesystem_changes(
    patch: str,
    *,
    default_filename: str | None = None,
    read_file_lf: Callable[[str], str] | None = None,
) -> tuple[list[tuple[str, str, str]], str]:
    """
    Build in-memory filesystem changes for a patch.

    read_file_lf(path) -> content_lf or raises FileNotFoundError
    Returns ([(path, action, content_lf), ...], status_message).
    On failure returns ([], EDIT_FAILED...).
    """
    try:
        sections = parse_file_patches(patch)
    except ValueError as exc:
        return [], str(exc)

    if not sections:
        return [], "EDIT_FAILED: patch contained no hunks."

    # Bare body with optional default filename
    if len(sections) == 1 and not sections[0].path:
        if not default_filename:
            return [], (
                "EDIT_FAILED: patch has no *** Update File / *** Add File headers "
                "and no filename was provided."
            )
        sections[0].path = default_filename

    changes: list[tuple[str, str, str]] = []
    summaries: list[str] = []

    for section in sections:
        path = section.path
        if not path:
            return [], "EDIT_FAILED: file section missing path."

        if section.action == "add":
            content = "\n".join(section.add_lines)
            if not section.add_lines and section.hunks:
                new_lines = [
                    ln.text for h in section.hunks for ln in h.lines if ln.kind == "+"
                ]
                content = "\n".join(new_lines)
            if content and not content.endswith("\n"):
                content += "\n"
            changes.append((path, "add", content))
            line_count = len(content.splitlines()) if content else 0
            summaries.append(f"add {path} ({line_count} lines)")
            continue

        if read_file_lf is None:
            return [], "EDIT_FAILED: cannot update file without reader."
        try:
            original = read_file_lf(path)
        except FileNotFoundError:
            return [], f"EDIT_FAILED: file not found: {path}"
        except OSError as exc:
            return [], f"EDIT_FAILED: cannot read {path}: {exc}"

        updated, message = apply_hunks_to_text(original, section.hunks)
        if updated is None:
            detail = (
                message
                if message.startswith("EDIT_FAILED:")
                else f"EDIT_FAILED: {message}"
            )
            return [], f"{detail}\n(while updating {path}; no files written)"
        changes.append((path, "update", updated))
        summaries.append(f"update {path}: {message}")

    return changes, "SUCCESS: " + "; ".join(summaries)


def replace_line_range(
    content_lf: str, start_line: int, end_line: int, new_content: str
) -> tuple[str | None, str]:
    """Replace inclusive 1-based line range with new_content (LF)."""
    ends_with_nl = content_lf.endswith("\n") if content_lf else True
    file_lines = content_lf.splitlines()
    n = len(file_lines)

    if start_line < 1 or end_line < start_line:
        return (
            None,
            f"EDIT_FAILED: invalid line range {start_line}-{end_line}.",
        )

    if n == 0:
        if start_line != 1:
            return None, "EDIT_FAILED: file is empty; use start_line=1."
        new_lf = new_content.replace("\r\n", "\n").replace("\r", "\n")
        if new_lf and not new_lf.endswith("\n"):
            new_lf += "\n"
        return new_lf, "SUCCESS: wrote contents into empty file."

    if end_line > n:
        return (
            None,
            f"EDIT_FAILED: end_line {end_line} out of range (file has {n} lines).",
        )

    new_lf = new_content.replace("\r\n", "\n").replace("\r", "\n")
    replacement = new_lf.splitlines()
    updated_lines = file_lines[: start_line - 1] + replacement + file_lines[end_line:]
    result = "\n".join(updated_lines)
    if ends_with_nl or content_lf.endswith("\n"):
        result += "\n"
    return result, (
        f"SUCCESS: replaced lines {start_line}-{end_line} "
        f"({end_line - start_line + 1} line(s)) with {len(replacement)} line(s)."
    )


def find_flexible_block(
    content_lf: str, old_string: str, *, line: int | None = None
) -> tuple[list[tuple[int, int]], str]:
    """
    Find line-index ranges [start, end) for old_string.

    Returns (list of (start_line_idx, end_line_idx), mode).
    """
    old_lf = old_string.replace("\r\n", "\n").replace("\r", "\n")
    if not old_lf:
        return [], "empty"

    file_lines = content_lf.splitlines()
    old_lines = old_lf.splitlines()
    if not old_lines:
        return [], "empty"

    # Exact line-block match first
    exact = _find_block(file_lines, old_lines, relaxed=False)
    mode = "exact-block"
    matches = exact
    if not matches:
        matches = _find_block(file_lines, old_lines, relaxed=True)
        mode = "whitespace-relaxed"

    if line is not None:
        matches = [m for m in matches if m <= line - 1 < m + len(old_lines)]

    return [(m, m + len(old_lines)) for m in matches], mode


def apply_string_replace(
    content_lf: str,
    old_string: str,
    new_string: str,
    *,
    line: int | None = None,
    replace_all: bool = False,
) -> tuple[str | None, str]:
    """Shared search/replace with exact then whitespace-relaxed matching."""
    old_lf = old_string.replace("\r\n", "\n").replace("\r", "\n")
    new_lf = new_string.replace("\r\n", "\n").replace("\r", "\n")
    if not old_lf:
        return None, "EDIT_FAILED: old_string is empty."

    file_lines = content_lf.splitlines()
    ends_with_nl = content_lf.endswith("\n")

    # Line-scoped single-line exact
    if line is not None:
        if not (1 <= line <= len(file_lines)):
            return (
                None,
                f"EDIT_FAILED: line {line} is out of range "
                f"(file has {len(file_lines)} lines). Read the file first.",
            )
        line_text = file_lines[line - 1]
        if old_lf in line_text:
            file_lines[line - 1] = line_text.replace(old_lf, new_lf, 1)
            result = "\n".join(file_lines)
            if ends_with_nl:
                result += "\n"
            return result, "SUCCESS: replaced 1 occurrence(s) (exact-line)."
        old_single = old_lf.splitlines()
        if len(old_single) == 1 and lines_equal_relaxed(line_text, old_single[0]):
            new_single = new_lf.splitlines() or [""]
            file_lines[line - 1] = new_single[0]
            result = "\n".join(file_lines)
            if ends_with_nl:
                result += "\n"
            return (
                result,
                "SUCCESS: replaced 1 occurrence(s) (whitespace-relaxed-line).",
            )
        return (
            None,
            f"EDIT_FAILED: old_string not found on line {line}.\n"
            f"Line {line} content:\n{line}|{line_text}\n"
            "Retry with apply_patch or replace_lines.",
        )

    # Exact substring
    count = content_lf.count(old_lf)
    if count == 1 or (replace_all and count >= 1):
        updated = (
            content_lf.replace(old_lf, new_lf)
            if replace_all
            else content_lf.replace(old_lf, new_lf, 1)
        )
        n = count if replace_all else 1
        return updated, f"SUCCESS: replaced {n} occurrence(s) (exact)."
    if count > 1 and not replace_all:
        # locate line numbers
        locs = []
        start = 0
        while True:
            idx = content_lf.find(old_lf, start)
            if idx < 0:
                break
            locs.append(content_lf.count("\n", 0, idx) + 1)
            start = idx + max(1, len(old_lf))
        loc_str = ", ".join(str(x) for x in locs[:8])
        return (
            None,
            f"EDIT_FAILED: old_string appears {count} times (lines {loc_str}). "
            "Pass `line`, set replace_all=true, or include more context. "
            "Prefer apply_patch for multi-location edits.",
        )

    # Flexible block match
    ranges, mode = find_flexible_block(content_lf, old_lf)
    if not ranges:
        # snippet hint: first line of old
        hint = old_lf.splitlines()[0][:80] if old_lf.splitlines() else ""
        hint_line = 0
        for i, fl in enumerate(file_lines):
            if hint and normalize_ws_line(fl) == normalize_ws_line(hint):
                hint_line = i
                break
        return (
            None,
            "EDIT_FAILED: old_string not found (exact and whitespace-relaxed).\n"
            "Looking for:\n"
            + "\n".join(f"  |{ln}" for ln in old_lf.splitlines()[:8])
            + f"\nNearby context:\n{_snippet(file_lines, hint_line)}\n"
            "Re-read the file, then retry with apply_patch or replace_lines.",
        )

    if len(ranges) > 1 and not replace_all:
        locs = ", ".join(str(s + 1) for s, _ in ranges[:8])
        return (
            None,
            f"EDIT_FAILED: old_string matches {len(ranges)} places (lines {locs}). "
            "Pass `line`, set replace_all=true, or use apply_patch with more context.",
        )

    new_lines = new_lf.splitlines()
    # Apply from bottom to top so indices stay valid
    for start, end in sorted(ranges if replace_all else ranges[:1], reverse=True):
        file_lines[start:end] = new_lines

    result = "\n".join(file_lines)
    if ends_with_nl:
        result += "\n"
    n = len(ranges) if replace_all else 1
    return result, f"SUCCESS: replaced {n} occurrence(s) ({mode})."
