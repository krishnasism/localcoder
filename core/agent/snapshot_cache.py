"""Short-lived project snapshot cache to avoid re-scanning every run."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from core.tools.shell import Shell

DEFAULT_TTL_SECONDS = 45.0


@dataclass
class _CachedSnapshot:
    files: str
    tree: str
    expires_at: float
    root_mtime: float


_CACHE: dict[str, _CachedSnapshot] = {}


def _root_mtime(root: str) -> float:
    try:
        return os.path.getmtime(root)
    except OSError:
        return 0.0


def clear_snapshot_cache() -> None:
    _CACHE.clear()


async def gather_project_snapshot(
    max_depth: int = 2,
    *,
    use_cache: bool = True,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> tuple[str, str, dict]:
    """
    Return (files_listing, directory_tree, timing_meta).

    Lists files and builds a shallow tree in parallel. Reuses a short-lived
    cache keyed by the current working directory when the root mtime is unchanged.
    """
    root = os.path.abspath(Shell.current_directory or os.getcwd())
    started = time.perf_counter()
    mtime = _root_mtime(root)
    now = time.time()

    if use_cache:
        cached = _CACHE.get(root)
        if (
            cached is not None
            and cached.expires_at > now
            and cached.root_mtime == mtime
        ):
            return (
                cached.files,
                cached.tree,
                {
                    "cache_hit": True,
                    "snapshot_ms": round((time.perf_counter() - started) * 1000, 1),
                    "root": root,
                },
            )

    files_raw, tree_raw = await asyncio.gather(
        Shell.list_files(),
        Shell.get_directory_tree(max_depth=max_depth),
    )

    if use_cache:
        _CACHE[root] = _CachedSnapshot(
            files=files_raw,
            tree=tree_raw,
            expires_at=now + ttl_seconds,
            root_mtime=mtime,
        )

    return (
        files_raw,
        tree_raw,
        {
            "cache_hit": False,
            "snapshot_ms": round((time.perf_counter() - started) * 1000, 1),
            "root": root,
        },
    )
