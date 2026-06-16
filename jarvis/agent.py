from __future__ import annotations

import json
import time
from typing import Any

from openai import BadRequestError, RateLimitError

from .client import JarvisClient
from .context import ContextManager, UsageTracker
from rich.markdown import Markdown
from .formatter import print_jarvis_header, make_live_markdown, console
from .context import is_plan_mode
from .permissions import is_auto_mode
from .logger import SessionLogger
from .permissions import needs_permission, request_permission
from .tools import get_all_tools, get_tool_by_name

_MAX_TOOL_ITERATIONS = 10
_RETRY_DELAYS = (5, 15, 30)  # seconds between attempts


def _is_context_length_error(e: BadRequestError) -> bool:
    msg = str(e).lower()
    return "context_length_exceeded" in msg or "maximum context length" in msg or "too many tokens" in msg


def _stream_with_retry(client: JarvisClient, messages: list, tools: list):
    for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            return list(client.stream(messages, tools=tools))
        except RateLimitError:
            if delay is None:
                raise
            console.print(f"[yellow]Rate limited — retrying in {delay}s...[/yellow]")
            time.sleep(delay)

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


_CONTEXT_WARN_TOKENS = 20_000  # warn at ~20K estimated tokens in history
_WRITE_TOOLS = {"write_file", "edit_file", "run_command"}


def run_agent(user_message: str, client: JarvisClient, context: ContextManager, tracker: UsageTracker, logger: SessionLogger | None = None) -> None:
    context.append({"role": "user", "content": user_message})
    if logger:
        logger.user(user_message)

    if context.token_estimate() > _CONTEXT_WARN_TOKENS:
        console.print(f"[yellow]⚠ Context is large (~{context.token_estimate():,} tokens). Run /compact to shrink it.[/yellow]")

    # In plan mode, track whether a plan has been shown before allowing writes
    plan_shown = not is_plan_mode()  # True means writes are allowed

    for iteration in range(_MAX_TOOL_ITERATIONS):
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        text_chunks: list[str] = []
        finish_reason: str | None = None
        streaming_started = False

        tool_schemas = [t.to_openai_schema() for t in get_all_tools()]
        try:
            chunks = _stream_with_retry(client, context.messages(), tool_schemas)
        except BadRequestError as e:
            if _is_context_length_error(e):
                console.print("[yellow]⚠ Context window full — compacting and continuing...[/yellow]")
                context.compact(client, tracker)
                try:
                    chunks = _stream_with_retry(client, context.messages(), tool_schemas)
                except Exception as retry_err:
                    console.print(f"[red]Error after compaction: {retry_err}[/red]")
                    return
            else:
                raise
        status = console.status("[dim]Thinking...[/dim]", spinner="dots")
        status.start()
        live = None

        for chunk in chunks:
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
                if live is None:
                    print_jarvis_header()
                    live = make_live_markdown()
                    live.start()
                text_chunks.append(delta.content)
                live.update(Markdown("".join(text_chunks)))

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

        if live:
            live.stop()
        else:
            status.stop()

        full_text = "".join(text_chunks)

        if finish_reason == "stop" or (finish_reason != "tool_calls" and not collected_tool_calls):
            console.print()
            context.append({"role": "assistant", "content": full_text})
            if logger:
                logger.assistant(full_text)
            return

        # Once the model has output text in plan mode, mark the plan as shown
        if full_text and not plan_shown:
            plan_shown = True

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

                # Plan mode gate — block write tools until a plan has been shown
                result: str | None = None
                if not plan_shown and tool_name in _WRITE_TOOLS:
                    result = (
                        "Plan mode is active. You must output a numbered plan first before "
                        "calling any write or command tools. Show the plan now, then execute "
                        "after the user types /go (or immediately if auto mode is on)."
                    )

                # Permission gate — show diff/warning and ask before proceeding
                if result is None and needs_permission(tool_name, args):
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
