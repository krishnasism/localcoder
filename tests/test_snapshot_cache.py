import asyncio
import os
import tempfile

from core.agent.snapshot_cache import clear_snapshot_cache, gather_project_snapshot
from core.tools.shell import Shell


def test_snapshot_cache_hit_and_parallel_gather():
    clear_snapshot_cache()
    td = tempfile.mkdtemp()
    original = os.getcwd()
    try:
        os.chdir(td)
        Shell.current_directory = td
        open(os.path.join(td, "a.py"), "w", encoding="utf-8").write("print(1)\n")

        files1, tree1, meta1 = asyncio.run(gather_project_snapshot(ttl_seconds=60))
        assert meta1["cache_hit"] is False
        assert "a.py" in files1 or "a.py" in tree1

        files2, tree2, meta2 = asyncio.run(gather_project_snapshot(ttl_seconds=60))
        assert meta2["cache_hit"] is True
        assert files2 == files1
        assert tree2 == tree1
    finally:
        clear_snapshot_cache()
        os.chdir(original)
        Shell.current_directory = os.path.dirname(os.path.abspath(__file__))
