"""
Build the Localcoder API into a single executable with PyInstaller.

Usage (from repo root, with venv active):
  python packaging/build_backend.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "application" / "resources" / "backend"
DIST_DIR = ROOT / "packaging" / "dist"
BUILD_DIR = ROOT / "packaging" / "build"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"]
        )

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    entry = ROOT / "packaging" / "api_entry.py"
    name = "localcoder-api"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        f"--name={name}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={BUILD_DIR}",
        f"--paths={ROOT}",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=api",
        "--hidden-import=main",
        "--hidden-import=core",
        "--hidden-import=core.code_agent",
        "--hidden-import=core.agent",
        "--hidden-import=core.tools",
        "--hidden-import=core.state",
        "--collect-all=uvicorn",
        "--collect-all=fastapi",
        "--collect-all=starlette",
        "--collect-submodules=core",
        str(entry),
    ]

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    exe_name = f"{name}.exe" if os.name == "nt" else name
    built = DIST_DIR / exe_name
    if not built.exists():
        # Non-Windows PyInstaller still uses the bare name
        built = DIST_DIR / name
    if not built.exists():
        raise SystemExit(f"Expected build output missing under {DIST_DIR}")

    target = OUT_DIR / built.name
    shutil.copy2(built, target)
    print(f"Backend binary copied to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
