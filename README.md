# Localcoder

A local desktop coding agent. Describe a change, and Localcoder plans, edits files in your project, and streams progress — powered by a local model (Ollama or any OpenAI-compatible server).

> Experimental / learning project. Useful for local agent workflows, not a production Cursor replacement.

## Features

- **Desktop app** (Electron + React) with a Cursor-style chat UI
- **Two-phase agent**: fast planning, then focused editing
- **Live streaming** of plans, tool calls, and results over SSE
- **Live status** in the UI (`Reading App.tsx…`, `Editing…`, etc.)
- **Anti-loop guards**: repeated tools blocked, limited planning reads, context compaction
- **OS-aware paths**: Windows / macOS / Linux separators normalized automatically
- **Robust edits**: CRLF-safe `sed`, plus `insert_after` for adding lines
- **Stop / cancel** in-flight runs from the UI
- **Standalone Windows packaging** (installer + bundled API) with GitHub Actions CI

## How it works

```
Electron UI  ──SSE──▶  FastAPI (api.py)  ──▶  CodeAgent  ──▶  Ollama / local LLM
                              │
                              └── filesystem tools (read, sed, insert_after, write, pytest, …)
```

1. **Planning** — short, read-only pass; produces a numbered file-level plan  
2. **Editing** — applies the plan with tools, then calls `finish`

## Requirements

- Python 3.11+
- Node.js 20+
- A local model server, e.g. [Ollama](https://ollama.com)

## Setup

### 1. Python backend

```sh
pip install uv
uv venv
```

Activate:

| OS | Command |
|----|---------|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

```sh
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
```

### 2. Local model (Ollama)

```sh
ollama pull qwen3-coder
```

Defaults:

| Variable | Default |
|----------|---------|
| `OPENAI_API_BASE_URL` | `http://localhost:11434/v1` |
| `OPENAI_API_KEY` | `local` |
| `LOCALCODER_MODEL` | `qwen3-coder` |
| `LOCALCODER_MAX_ITERATIONS` | `25` (editing) |
| `LOCALCODER_PLANNING_MAX_ITERATIONS` | `5` |

### 3. Run in development

Terminal 1 — API:

```sh
uvicorn api:app --reload
```

API: `http://127.0.0.1:8000` (`GET /health` to check).

Terminal 2 — desktop app:

```sh
cd application
npm install
npm run dev
```

In the app:

1. Set the **project path** (Settings or context pill)
2. Pick a **model**
3. Type what you want changed and press **Enter** (Shift+Enter for newline)
4. Watch plan → tools → result; use **Stop** to cancel

## Project layout

| Path | Role |
|------|------|
| `application/` | Electron + React + Vite UI |
| `api.py` | FastAPI + SSE streaming |
| `core/code_agent.py` | Agent loop (plan → edit) |
| `core/agent/` | Prompts, config, loop helpers |
| `core/tools/` | Filesystem / shell / pytest tools |
| `packaging/` | PyInstaller backend build for standalone |
| `.github/workflows/` | CI build + release pipelines |
| `tests/` | pytest suite |

## Tests

```sh
pytest -q
```

## Package as a standalone app

Builds the Electron UI **and** a bundled FastAPI binary so you can share an installer.

### macOS

```sh
# From repo root (venv active)
python packaging/build_backend.py

cd application
npm install
npm run make:mac
```

Outputs in `application/out/make/`:

- `Localcoder-<version>-arm64.dmg` (or `x64`) — disk image installer
- `zip/darwin/...` — portable zip

> **Note:** macOS may show a Gatekeeper warning for unsigned builds. Right-click the `.app` and choose **Open** to bypass it the first time.

### Windows

```sh
# From repo root (venv active)
python packaging/build_backend.py

cd application
npm install
npm run make:win
```

Outputs in `application/out/make/`:

- `LocalcoderSetup.exe` — installer (best for sharing)
- `zip/win32/...` — portable zip

The packaged app starts the API automatically on both platforms. Users still need Ollama (or another compatible server) running locally.

### CI / CD

| Workflow | Trigger | Output |
|----------|---------|--------|
| [`.github/workflows/build.yml`](.github/workflows/build.yml) | push / PR | Windows artifacts |
| [`.github/workflows/release.yml`](.github/workflows/release.yml) | tag `v*` or manual | GitHub Release with `.exe` |

```sh
git tag v1.0.0
git push origin v1.0.0
```

Or run **Release** from the Actions tab.

**Notes**

- Unsigned Windows builds may trigger SmartScreen until you add code signing.
- Unsigned macOS builds show a Gatekeeper prompt; right-click → Open to run them.
- CI currently focuses on Windows `.exe`; macOS builds run locally with `npm run make:mac`.

## Tips

- Prefer absolute project paths.
- Keep prompts concrete (“Add a dark-mode toggle in the sidebar”) for faster planning.
- If edits fail, the agent should re-read and retry; `insert_after` is preferred for adding new lines in two different places (one call per location).
