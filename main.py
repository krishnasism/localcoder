import argparse
from core.code_agent import CodeAgent


def explain_code(query, path):
    agent = CodeAgent()
    explanation = agent.explain_code(query, path)
    return explanation


def generate_code(query, path):
    agent = CodeAgent()
    agent.generate_code(query, path)


def main():
    parser = argparse.ArgumentParser(description="Explain code using CodeAgent")

    parser.add_argument(
        "command", help="Command to run (supported: explain_code, generate_code)"
    )

    parser.add_argument("--query", required=True, help="Enter your query")

    parser.add_argument("--path", required=True, help="Enter the path to the code file")

    args = parser.parse_args()

    if args.command == "explain_code":
        explanation = explain_code(args.query, args.path)
        print(explanation)
    elif args.command == "generate_code":
        generate_code(args.query, args.path)
    else:
        print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
