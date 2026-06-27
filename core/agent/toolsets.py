from dataclasses import dataclass

from core.tools.tools import (
    FS_READ_ONLY_TOOLS,
    FS_TOOLS,
    READ_ONLY_TOOL_REGISTRATIONS,
    TOOL_REGISTRATIONS,
)


@dataclass
class AgentToolRegistry:
    file_system_tools: list
    editing_tools: list
    read_only_file_system_tools: list
    read_only_planning_tools: list
    tool_registrations: dict
    read_only_tool_registrations: dict


def build_tool_registry(finish_fn, plan_finish_fn) -> AgentToolRegistry:
    file_system_tools = list(FS_TOOLS)
    file_system_tools.append({"type": "function", "function": finish_fn})

    editing_tools = [
        tool
        for tool in file_system_tools
        if tool["function"]["name"] not in {"list_files", "get_directory_tree"}
    ]

    read_only_file_system_tools = list(FS_READ_ONLY_TOOLS)
    read_only_file_system_tools.append({"type": "function", "function": plan_finish_fn})
    read_only_planning_tools = [
        tool
        for tool in read_only_file_system_tools
        if tool["function"]["name"] not in {"list_files", "get_directory_tree"}
    ]

    tool_registrations = dict(TOOL_REGISTRATIONS)
    tool_registrations["finish"] = finish_fn

    read_only_tool_registrations = dict(READ_ONLY_TOOL_REGISTRATIONS)
    read_only_tool_registrations["plan_finish"] = plan_finish_fn

    return AgentToolRegistry(
        file_system_tools=file_system_tools,
        editing_tools=editing_tools,
        read_only_file_system_tools=read_only_file_system_tools,
        read_only_planning_tools=read_only_planning_tools,
        tool_registrations=tool_registrations,
        read_only_tool_registrations=read_only_tool_registrations,
    )
