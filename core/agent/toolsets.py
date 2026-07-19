from dataclasses import dataclass

from core.tools.shell import Shell
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
    lean_editing_tools: list
    read_only_file_system_tools: list
    read_only_planning_tools: list
    tool_registrations: dict
    read_only_tool_registrations: dict


_LEAN_EDITING_ALLOW = frozenset(
    {
        "read_file",
        "apply_patch",
        "search_replace",
        "replace_lines",
        "write_file",
        "finish",
    }
)


def build_tool_registry(finish_fn, plan_finish_fn) -> AgentToolRegistry:
    file_system_tools = list(FS_TOOLS)
    file_system_tools.append({"type": "function", "function": finish_fn})

    editing_tools = [
        tool
        for tool in file_system_tools
        if tool["function"]["name"] not in {"list_files", "get_directory_tree"}
    ]
    lean_editing_tools = [
        tool
        for tool in editing_tools
        if tool["function"]["name"] in _LEAN_EDITING_ALLOW
    ]

    read_only_file_system_tools = list(FS_READ_ONLY_TOOLS)
    read_only_file_system_tools.append({"type": "function", "function": plan_finish_fn})

    # Keep planning lean: snapshot is preloaded, so only allow focused reads + finish.
    planning_allow = {
        "read_file",
        "find_files",
        "search_text_in_files",
        "plan_finish",
    }
    # find_files / search live on the full tool list — attach if present.
    planning_extra = [
        tool
        for tool in FS_TOOLS
        if tool["function"]["name"] in {"find_files", "search_text_in_files"}
    ]
    read_only_planning_tools = [
        tool
        for tool in read_only_file_system_tools + planning_extra
        if tool["function"]["name"] in planning_allow
    ]
    # Deduplicate by name while preserving order.
    seen: set[str] = set()
    deduped_planning = []
    for tool in read_only_planning_tools:
        name = tool["function"]["name"]
        if name in seen:
            continue
        seen.add(name)
        deduped_planning.append(tool)
    read_only_planning_tools = deduped_planning

    tool_registrations = dict(TOOL_REGISTRATIONS)
    tool_registrations["finish"] = finish_fn

    read_only_tool_registrations = dict(READ_ONLY_TOOL_REGISTRATIONS)
    read_only_tool_registrations["plan_finish"] = plan_finish_fn
    read_only_tool_registrations["find_files"] = Shell.find_files
    read_only_tool_registrations["search_text_in_files"] = Shell.search_text_in_files

    return AgentToolRegistry(
        file_system_tools=file_system_tools,
        editing_tools=editing_tools,
        lean_editing_tools=lean_editing_tools,
        read_only_file_system_tools=read_only_file_system_tools,
        read_only_planning_tools=read_only_planning_tools,
        tool_registrations=tool_registrations,
        read_only_tool_registrations=read_only_tool_registrations,
    )
