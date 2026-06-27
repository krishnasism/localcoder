from openai import OpenAI
import os
from dotenv import load_dotenv
from core.tools.tools import FS_TOOLS, TOOL_REGISTRATIONS
from core.state.state import AgentStateManager
from dataclasses import dataclass, field
import json

SYSTEM_PROMPT = """
You are an autonomous software engineer.

Your objective is to modify the user's project.

Rules:
- Never assume file contents.
- Always inspect the project before editing.
- Read files before making changes.
- Prefer minimal edits.
- Use available tools whenever needed.
- Verify your changes after editing.
- Continue working until the task is complete.
- Only finish once the requested modification has been made.

Recommended workflow:

1. Inspect project
2. Read relevant files
3. Modify code
4. Verify modifications
5. Finish
"""


@dataclass
class AgentContext:
    messages: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    working_directory: str = ""
    current_task: str = ""

    iteration: int = 0
    max_iterations: int = 20


class CodeAgent:
    def __init__(self):
        load_dotenv()
        # self.model = "llama3.2"  #
        self.model = "qwen3.6"
        self.client = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "local"),
        )
        self.file_system_tools = FS_TOOLS
        self.tool_registrations = TOOL_REGISTRATIONS
        self.agent_state_manager = AgentStateManager()

    def __call_llm(self, context: AgentContext) -> str:
        return self.client.chat.completions.create(
            model=self.model,
            messages=context.messages,
            tools=self.file_system_tools,
        )

    def _execute_tool(self, tool_call):
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        print(f"Running tool: {tool_name}")

        fn = self.tool_registrations.get(tool_name)

        if fn is None:
            raise ValueError(f"Unknown tool '{tool_name}'")

        return fn(**args)

    def generate_code(self, prompt: str, path: str) -> str:
        context = AgentContext(
            current_task=prompt,
            working_directory=os.getcwd(),
        )
        context.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {"role": "user", "content": f"{prompt}\nTarget file: {path}"},
        ]

        self.agent_state_manager.update_state("initializing")
        while context.iteration < context.max_iterations:
            context.iteration += 1
            print(f"Iteration {context.iteration} of {context.max_iterations}")
            self.agent_state_manager.update_state("editing")
            response = self.__call_llm(context)
            message = response.choices[0].message
            context.messages.append(message)

            if message.content:
                print(f"LLM Response: {message.content}")

            if not message.tool_calls:
                print("No tool calls in the response. Assuming task is complete.")
                self.agent_state_manager.update_state("completed")
                return message.content

            for tool_call in message.tool_calls:
                try:
                    result = self._execute_tool(tool_call)
                    context.tool_results[tool_call.id] = result
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(result),
                            "tool_call_id": tool_call.id,
                        }
                    )
                except Exception as e:
                    error_message = (
                        f"Error executing tool '{tool_call.function.name}': {str(e)}"
                    )
                    self.agent_state_manager.update_state("error")
                    context.messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps({"error": error_message}),
                            "tool_call_id": tool_call.id,
                        }
                    )

    def explain_code(self, query: str, path: str) -> str:
        with open(path, "r") as file:
            code_content = file.read()
        return self.__call_llm(
            system="You are a helpful assistant that explains code.",
            user=f"Query: {query}\nCode:\n{code_content}",
        )
