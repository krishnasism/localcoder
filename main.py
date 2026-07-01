import argparse
import asyncio
import os
import shutil
import subprocess
import threading
from typing import IO
from core.code_agent import CodeAgent


def _resolve_shell_execution(command: str):
    if os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if powershell:
            return [powershell, "-NoProfile", "-Command", command], "powershell"
        return ["cmd", "/C", command], "cmd"

    unix_shell = os.getenv("SHELL")
    if not unix_shell:
        unix_shell = (
            "/bin/zsh"
            if os.path.exists("/bin/zsh")
            else "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
        )
    return [unix_shell, "-lc", command], os.path.basename(unix_shell)


def _run_shell_command_sync(
    exec_args: list[str],
    working_directory: str,
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        exec_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=working_directory,
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout or b"", stderr or b""


def _start_shell_process(
    exec_args: list[str],
    working_directory: str,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        exec_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=working_directory,
    )


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


async def explain_code(query, path, model=None):
    agent = CodeAgent()
    if model is not None:
        agent.model = model
    explanation = await agent.explain_code(query, path)
    return explanation


async def generate_code(query, path, model=None):
    agent = CodeAgent()
    if model is not None:
        agent.model = model
    await agent.generate_code(query, path)


async def generate_code_stream(query, path, model=None):
    agent = CodeAgent()
    if model is not None:
        agent.model = model
    async for event in agent.generate_code_stream(query, path):
        yield event


async def execute_shell_command(command: str, cwd: str | None = None):
    working_directory = cwd or os.getcwd()
    exec_args, shell_name = _resolve_shell_execution(command)

    returncode, stdout, stderr = await asyncio.to_thread(
        _run_shell_command_sync,
        exec_args,
        working_directory,
    )

    return {
        "shell": shell_name,
        "cwd": working_directory,
        "stdout": stdout.decode(errors="ignore"),
        "stderr": stderr.decode(errors="ignore"),
        "returncode": returncode,
    }


MONITORING_SYSTEM_PROMPT = """You are a local monitoring assistant helping the user watch shell command output in real time.

Given the command being run and the live output so far, respond with:
1. What the command does and what signals to watch for
2. What the current output means (patterns, errors, healthy vs unhealthy signs)
3. Concrete next steps or commands to try if something looks wrong

Be concise, practical, and action-oriented. If output is empty or just starting, explain what to expect next."""


async def analyze_monitoring_logs_stream(
    command: str,
    logs: str,
    cwd: str | None = None,
    model: str | None = None,
):
    agent = CodeAgent()
    if model is not None:
        agent.model = model

    trimmed_logs = logs[-8000:] if logs else "(no output yet)"
    user_content = (
        f"Command: {command}\n"
        f"Working directory: {cwd or '(default)'}\n\n"
        f"Live output:\n{trimmed_logs}"
    )

    try:
        stream = await agent.client.chat.completions.create(
            model=agent.model,
            messages=[
                {"role": "system", "content": MONITORING_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            stream=True,
            timeout=120.0,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield {"type": "insight_delta", "content": delta}

        yield {"type": "insight_done"}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        if "connection" in message.lower() or "connect" in message.lower():
            message = (
                f"Could not reach the model server ({agent.config.openai_base_url}). "
                "Make sure Ollama is running, then try again."
            )
        yield {"type": "insight_error", "message": message}


async def execute_shell_command_stream(command: str, cwd: str | None = None):
    working_directory = cwd or os.getcwd()
    exec_args, shell_name = _resolve_shell_execution(command)

    yield {
        "type": "start",
        "shell": shell_name,
        "cwd": working_directory,
    }

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
    process = _start_shell_process(exec_args, working_directory)

    def _pump_stream(stream: IO[bytes] | None, stream_name: str) -> None:
        try:
            if stream is not None:
                while True:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        (stream_name, chunk.decode(errors="ignore")),
                    )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, (stream_name, None))

    stdout_thread = threading.Thread(
        target=_pump_stream,
        args=(process.stdout, "stdout"),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_pump_stream,
        args=(process.stderr, "stderr"),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    closed_streams = 0
    try:
        while closed_streams < 2:
            stream_name, data = await queue.get()
            if data is None:
                closed_streams += 1
                continue
            yield {
                "type": stream_name,
                "content": data,
            }

        returncode = await asyncio.to_thread(process.wait)
        yield {
            "type": "end",
            "returncode": returncode,
        }
    except asyncio.CancelledError:
        await asyncio.to_thread(_terminate_process, process)
        raise
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)


async def main():
    parser = argparse.ArgumentParser(description="Explain code using CodeAgent")

    parser.add_argument(
        "command", help="Command to run (supported: explain_code, generate_code)"
    )

    parser.add_argument("--query", required=True, help="Enter your query")

    parser.add_argument("--path", required=True, help="Enter the path to the code file")

    args = parser.parse_args()

    if args.command == "explain_code":
        explanation = await explain_code(args.query, args.path)
        print(explanation)
    elif args.command == "generate_code":
        await generate_code(args.query, args.path)
    else:
        print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    asyncio.run(main())
