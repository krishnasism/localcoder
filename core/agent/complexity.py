"""Heuristic prompt complexity classification for fast-path routing."""

from __future__ import annotations

import re
from typing import Literal

Complexity = Literal["trivial", "medium", "hard"]

_FILE_PATH_RE = re.compile(
    r"(?:^|[\s`\"'(])"
    r"(?P<path>(?:[A-Za-z0-9_.\-]+[/\\])*[A-Za-z0-9_.\-]+\."
    r"(?:tsx?|jsx?|py|css|scss|html?|md|json|ya?ml|toml|rs|go|java|kt|vue|svelte))\b",
    re.IGNORECASE,
)

_TRIVIAL_RE = re.compile(
    r"\b("
    r"rename|typo|fix\s+typo|replace|change|update|set|toggle|"
    r"remove|delete|add\s+class|css|label|title|comment|wording|copy|"
    r"capitalize|lowercase|uppercase|whitespace|spacing|color|theme|"
    r"night\s*mode|dark\s*mode|button\s+text"
    r")\b",
    re.IGNORECASE,
)

_HARD_RE = re.compile(
    r"\b("
    r"refactor|redesign|migrate|rewrite|architect(?:ure)?|"
    r"multi[- ]?file|across\s+(the\s+)?(codebase|project|app)|"
    r"entire|whole\s+(app|project|codebase)|from\s+scratch|"
    r"end[- ]to[- ]end|implement\s+(a|an|the)\s+\w+|"
    r"new\s+feature|build\s+(a|an|the)|add\s+support\s+for|"
    r"overhaul|restructure"
    r")\b",
    re.IGNORECASE,
)

_MULTI_FILE_HINT = re.compile(
    r"\b(files?|modules?|components?)\b.*\b(and|,)\b|\bin\s+.+\s+and\s+.+\.",
    re.IGNORECASE,
)


def classify_prompt(prompt: str) -> Complexity:
    """Classify a user prompt so the agent can skip or shorten planning."""
    text = (prompt or "").strip()
    if not text:
        return "medium"

    if _HARD_RE.search(text) or len(text) > 600 or text.count("\n") > 12:
        return "hard"

    has_file = bool(_FILE_PATH_RE.search(text))
    trivial_signal = bool(_TRIVIAL_RE.search(text))
    multi_file = bool(_MULTI_FILE_HINT.search(text))

    if (
        has_file
        and trivial_signal
        and not multi_file
        and len(text) < 280
        and text.count("\n") < 6
    ):
        return "trivial"

    if has_file or (trivial_signal and len(text) < 200) or len(text) < 160:
        return "medium"

    return "hard"


def synthetic_plan_for_prompt(prompt: str) -> str:
    """Build a short execution plan when planning is skipped."""
    text = " ".join((prompt or "").strip().split())
    if not text:
        return "1. Inspect the mentioned files\n2. Apply the requested change\n3. Finish"
    files = [m.group("path") for m in _FILE_PATH_RE.finditer(prompt or "")]
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_files: list[str] = []
    for path in files:
        key = path.replace("\\", "/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique_files.append(path)

    lines = ["1. Read the target file(s) only if needed"]
    if unique_files:
        joined = ", ".join(unique_files[:4])
        lines.append(f"2. Apply the requested change in: {joined}")
    else:
        lines.append(f"2. Apply the requested change: {text[:180]}")
    lines.append("3. Call finish when done")
    return "\n".join(lines)
