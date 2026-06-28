import argparse
import asyncio
from core.code_agent import CodeAgent


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
