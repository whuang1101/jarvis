from __future__ import annotations

import json
from typing import Any

from .client import JarvisClient
from .context import ContextManager, UsageTracker
from .formatter import print_streaming_token, console
from .logger import SessionLogger
from .permissions import needs_permission, request_permission
from .tools import get_all_tools, get_tool_by_name

_MAX_TOOL_ITERATIONS = 10

_TOOL_VERBS = {
    "read_file": "Reading",
    "write_file": "Writing",
    "edit_file": "Editing",
    "list_dir": "Listing",
    "search_files": "Searching",
    "run_command": "Running",
    "git_status": "git status",
    "git_diff": "git diff",
    "git_log": "git log",
    "web_search": "Searching web",
    "web_extract": "Extracting",
    "fetch_url": "Fetching",
    "find_symbol": "Finding",
    "package_info": "Looking up",
}


def _tool_status_label(tool_name: str, args: dict[str, Any]) -> str:
    verb = _TOOL_VERBS.get(tool_name, tool_name)
    if "path" in args:
        return f"{verb} {args['path']}"
    if "command" in args:
        cmd = args["command"]
        return f"{verb}: {cmd[:60]}{'...' if len(cmd) > 60 else ''}"
    if "pattern" in args:
        return f"{verb}: {args['pattern']}"
    first_val = str(next(iter(args.values()), ""))
    return f"{verb} {first_val[:60]}"


def run_agent(user_message: str, client: JarvisClient, context: ContextManager, tracker: UsageTracker, logger: SessionLogger | None = None) -> None:
    context.append({"role": "user", "content": user_message})
    if logger:
        logger.user(user_message)

    for iteration in range(_MAX_TOOL_ITERATIONS):
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        text_chunks: list[str] = []
        finish_reason: str | None = None
        streaming_started = False

        tool_schemas = [t.to_openai_schema() for t in get_all_tools()]
        with console.status("[dim]Thinking...[/dim]", spinner="dots") as status:
            for chunk in client.stream(context.messages(), tools=tool_schemas):
                if chunk.usage:
                    tracker.record(chunk.usage.prompt_tokens, chunk.usage.completion_tokens, client.current_deployment())

                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                finish_reason = choice.finish_reason
                delta = choice.delta

                if not streaming_started and (delta.content or delta.tool_calls):
                    status.stop()
                    streaming_started = True

                if delta.content:
                    text_chunks.append(delta.content)
                    print_streaming_token(delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name if tc.function else "",
                                "arguments": "",
                            }
                        if tc.id:
                            collected_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                collected_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                collected_tool_calls[idx]["arguments"] += tc.function.arguments

        full_text = "".join(text_chunks)

        if finish_reason == "stop" or (finish_reason != "tool_calls" and not collected_tool_calls):
            if full_text:
                console.print()
            context.append({"role": "assistant", "content": full_text})
            if logger:
                logger.assistant(full_text)
            return

        if collected_tool_calls:
            if full_text:
                console.print()

            tool_calls_msg: list[dict[str, Any]] = []
            for tc in collected_tool_calls.values():
                tool_calls_msg.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })
            context.append({"role": "assistant", "content": full_text or None, "tool_calls": tool_calls_msg})

            for tc in collected_tool_calls.values():
                tool_name = tc["name"]
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                label = _tool_status_label(tool_name, args)
                if logger:
                    logger.tool_call(tool_name, args)

                # Permission gate — show diff/warning and ask before proceeding
                result: str | None = None
                if needs_permission(tool_name, args):
                    result = request_permission(tool_name, args)

                if result is None:
                    tool = get_tool_by_name(tool_name)
                    if tool is None:
                        result = f"Error: unknown tool '{tool_name}'"
                        console.print(f"[dim]  ✗ {label}[/dim]")
                    else:
                        with console.status(f"[dim]{label}[/dim]", spinner="dots"):
                            try:
                                result = tool.execute(args)
                            except Exception as e:
                                result = f"Error executing {tool_name}: {e}"
                        console.print(f"[dim]  ✓ {label}[/dim]")

                if logger:
                    logger.tool_result(tool_name, result)

                context.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

    console.print()
    console.print("[yellow]Warning: reached max tool iterations (10), stopping.[/yellow]")
