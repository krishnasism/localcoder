from openai import OpenAI
import os
from dotenv import load_dotenv
from core.tools.tools import FS_TOOLS, TOOL_REGISTRATIONS
from core.state.state import AgentStateManager
import json

class CodeAgent:
    def __init__(self):
        load_dotenv()
        self.model = "llama3.2"
        self.client = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "local"),
        )
        self.file_system_tools = FS_TOOLS
        self.tool_registrations = TOOL_REGISTRATIONS
        self.agent_state_manager = AgentStateManager()
        self.code_editing_workflow = [
            "initializing",
            "editing",
            "reviewing",
            "testing",
            "committing",
        ]

    def __call_llm(self, system: str, user: str, tools: list = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=tools if tools else None,
        )
        return response.choices[0].message.content.strip()

    def generate_code(self, prompt: str) -> str:
        self.agent_state_manager.update_state("initializing")

        messages = [
            {
                "role": "system",
                "content": "You are a code editing agent with tool access. Respond with code or tool calls as needed.",
            },
            {"role": "user", "content": prompt},
        ]

        self.agent_state_manager.update_state("editing")

        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.file_system_tools,
            )

            message = response.choices[0].message

            # CASE 1: final answer
            if not message.tool_calls:
                self.agent_state_manager.update_state("reviewing")

                final_output = message.content.strip()

                self.agent_state_manager.update_state("testing")
                # optionally run validation tools here

                self.agent_state_manager.update_state("committing")
                return final_output

            # CASE 2: tool execution
            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                try:
                    result = self.tool_registrations[tool_name](**args)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result),
                        }
                    )

                except Exception as e:
                    self.agent_state_manager.update_state("error")
                    raise e

    def explain_code(self, query: str, path: str) -> str:
        with open(path, "r") as file:
            code_content = file.read()
        return self.__call_llm(
            system="You are a helpful assistant that explains code.",
            user=f"Query: {query}\nCode:\n{code_content}",
        )
