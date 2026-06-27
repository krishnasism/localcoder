import os


def assistant_message_to_dict(message) -> dict:
    assistant_message = {
        "role": "assistant",
        "content": message.content or "",
    }
    if message.tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return assistant_message


def resolve_target_directory(path: str) -> str:
    candidate = os.path.abspath(path)
    if os.path.isfile(candidate):
        return os.path.dirname(candidate)
    return candidate


def truncate_for_context(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"
