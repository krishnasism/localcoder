"""Entry point for the packaged Localcoder API (PyInstaller)."""

from __future__ import annotations

import os
import sys


def _prepare_path() -> None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller onefile unpack dir
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if base not in sys.path:
        sys.path.insert(0, base)


def main() -> None:
    _prepare_path()
    import uvicorn

    host = os.environ.get("LOCALCODER_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LOCALCODER_API_PORT", "8000"))
    uvicorn.run("api:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
