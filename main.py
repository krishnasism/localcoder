import argparse
import asyncio
import os
import re
from core.code_agent import CodeAgent


_CD_COMMAND_RE = re.compile(
    r"^\s*(?:cd|chdir|set-location|sl)\s*(.*)\s*;?\s*$",
    re.IGNORECASE,
)


def _strip_path_quotes(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in ('"', "'"):
        return path[1:-1]
    return path


def _resolve_cd_command(command: str, working_directory: str) -> dict | None:
    match = _CD_COMMAND_RE.fullmatch(command)
    if not match:
        return None

    target = _strip_path_quotes(match.group(1).strip())
    if not target:
        target = os.path.expanduser("~")
    elif target == "-":
        return {
            "shell": "builtin",
            "cwd": working_directory,
            "stdout": "",
            "stderr": (
                "cd - is not supported in this session. "
                "Update the working directory field instead.\n"
            ),
            "returncode": 1,
        }

    new_path = (
        os.path.normpath(target)
        if os.path.isabs(target)
        else os.path.normpath(os.path.join(working_directory, target))
    )

    if not os.path.isdir(new_path):
        return {
            "shell": "builtin",
            "cwd": working_directory,
            "stdout": "",
            "stderr": f"The system cannot find the path specified: {target}\n",
            "returncode": 1,
        }

    resolved = os.path.abspath(new_path)
    return {
        "shell": "builtin",
        "cwd": resolved,
        "stdout": f"{resolved}\n",
        "stderr": "",
        "returncode": 0,
    }


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


async def generate_code_stream(query, path, model=None, cancel_event=None):
    agent = CodeAgent()
    if model is not None:
        agent.model = model
    async for event in agent.generate_code_stream(
        query, path, cancel_event=cancel_event
    ):
        yield event


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
