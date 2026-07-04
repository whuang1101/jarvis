from __future__ import annotations

import json
import time
from typing import Any

from openai import BadRequestError, RateLimitError

from .client import JarvisClient
from .context import ContextManager, UsageTracker
from .formatter import (
    print_jarvis_header, make_live_markdown, render_markdown_block,
    print_tool_use, print_tool_result, console,
)
from .logger import SessionLogger
from .permissions import needs_permission, request_permission
from .tools import get_all_tools, get_tool_by_name

_MAX_TOOL_ITERATIONS = 40
_RETRY_DELAYS = (5, 15, 30)  # seconds between attempts
_TOOL_TIMEOUT_SECS = 60
_MAX_TOOL_RESULT_CHARS = 8_000
_AUTOCOMPACT_TOKENS = 25_000


def truncate_tool_result(result: str, limit: int = _MAX_TOOL_RESULT_CHARS) -> str:
    """Cap any tool result so one huge output can't blow up the context window."""
    if len(result) <= limit:
        return result
    omitted = len(result) - 6_000 - 1_500
    return (
        result[:6_000]
        + f"\n[truncated — {omitted:,} chars omitted]\n"
        + result[-1_500:]
    )


def execute_with_timeout(tool: Any, args: dict[str, Any], timeout: int = _TOOL_TIMEOUT_SECS) -> str:
    """Run tool.execute in a worker thread; return an error string on timeout."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(tool.execute, args)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            future.cancel()
            return f"Error: tool timed out after {timeout}s"


def _is_context_length_error(e: BadRequestError) -> bool:
    msg = str(e).lower()
    return "context_length_exceeded" in msg or "maximum context length" in msg or "too many tokens" in msg


def _stream_with_retry(client: JarvisClient, messages: list, tools: list):
    """Yield streaming chunks lazily so they render in real time.

    The request is initiated (and RateLimitError surfaces) when iteration begins;
    `yield from` then forwards SSE chunks as they arrive instead of buffering the
    whole response with list(). BadRequestError is left to propagate to the caller.
    """
    for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            stream = client.stream(messages, tools=tools)
        except RateLimitError:
            if delay is None:
                raise
            console.print(f"[yellow]Rate limited — retrying in {delay}s...[/yellow]")
            time.sleep(delay)
            continue
        yield from stream
        return

# Claude-Code-style display names: rendered as ⏺ Name(arg)
_TOOL_VERBS = {
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "list_dir": "List",
    "search_files": "Search",
    "run_command": "Bash",
    "git_status": "GitStatus",
    "git_diff": "GitDiff",
    "git_log": "GitLog",
    "web_search": "WebSearch",
    "web_extract": "WebExtract",
    "fetch_url": "Fetch",
    "find_symbol": "FindSymbol",
    "package_info": "PackageInfo",
}


def _tool_status_label(tool_name: str, args: dict[str, Any]) -> str:
    verb = _TOOL_VERBS.get(tool_name, tool_name)
    for key in ("path", "command", "pattern", "symbol", "url", "query"):
        if key in args:
            val = str(args[key])
            return f"{verb}({val[:80]}{'…' if len(val) > 80 else ''})"
    first_val = str(next(iter(args.values()), ""))
    return f"{verb}({first_val[:80]})" if first_val else f"{verb}()"


_CONTEXT_WARN_TOKENS = 20_000  # warn at ~20K estimated tokens in history


def _accumulate_tool_calls(collected: dict[int, dict[str, Any]], tool_calls: Any) -> None:
    """Merge streamed tool_call fragments (which arrive split across chunks) by index."""
    for tc in tool_calls:
        idx = tc.index
        if idx not in collected:
            collected[idx] = {
                "id": tc.id or "",
                "name": tc.function.name if tc.function else "",
                "arguments": "",
            }
        if tc.id:
            collected[idx]["id"] = tc.id
        if tc.function:
            if tc.function.name:
                collected[idx]["name"] = tc.function.name
            if tc.function.arguments:
                collected[idx]["arguments"] += tc.function.arguments


def _stream_turn(
    client: JarvisClient, context: ContextManager, tracker: UsageTracker
) -> tuple[str, dict[int, dict[str, Any]], str | None]:
    """Stream one model response, rendering tokens live as they arrive.

    Returns (full_text, collected_tool_calls, finish_reason). RateLimitError is
    retried inside _stream_with_retry; a context_length_exceeded error triggers a
    one-time compaction and re-stream. Returns empty results if recovery fails.
    """
    tool_schemas = [t.to_openai_schema() for t in get_all_tools()]
    state: dict[str, Any] = {"text": [], "tools": {}, "finish": None, "started": False, "live": None}

    def drain(chunks: Any, status: Any) -> None:
        for chunk in chunks:
            if chunk.usage:
                tracker.record(chunk.usage.prompt_tokens, chunk.usage.completion_tokens, client.current_deployment())
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            state["finish"] = choice.finish_reason
            delta = choice.delta
            if not state["started"] and (delta.content or delta.tool_calls):
                status.stop()
                state["started"] = True
            if delta.content:
                if state["live"] is None:
                    print_jarvis_header()
                    state["live"] = make_live_markdown()
                    state["live"].start()
                state["text"].append(delta.content)
                state["live"].update(render_markdown_block("".join(state["text"])))
            if delta.tool_calls:
                _accumulate_tool_calls(state["tools"], delta.tool_calls)

    def stop(status: Any) -> None:
        if state["live"]:
            state["live"].stop()
        else:
            status.stop()

    status = console.status("[dim]Thinking...[/dim]", spinner="dots")
    status.start()
    try:
        drain(_stream_with_retry(client, context.messages(), tool_schemas), status)
    except KeyboardInterrupt:
        # Keep the partial text; drop any half-received tool calls (they'd be
        # incomplete JSON). The caller stores this as a normal assistant turn.
        stop(status)
        console.print("\n[yellow]⨯ Interrupted[/yellow]")
        partial = "".join(state["text"])
        if partial:
            partial += "\n\n[interrupted by user]"
        return partial, {}, "stop"
    except BadRequestError as e:
        stop(status)
        if not _is_context_length_error(e):
            raise
        console.print("[yellow]⚠ Context window full — compacting and continuing...[/yellow]")
        context.compact(client, tracker)
        state.update({"text": [], "tools": {}, "finish": None, "started": False, "live": None})
        status = console.status("[dim]Thinking...[/dim]", spinner="dots")
        status.start()
        try:
            drain(_stream_with_retry(client, context.messages(), tool_schemas), status)
        except Exception as retry_err:
            stop(status)
            console.print(f"[red]Error after compaction: {retry_err}[/red]")
            return "", {}, None

    stop(status)
    return "".join(state["text"]), state["tools"], state["finish"]


def run_agent(user_message: str, client: JarvisClient, context: ContextManager, tracker: UsageTracker, logger: SessionLogger | None = None) -> None:
    # Compact BEFORE appending the new user message so it isn't folded into the summary.
    if context.token_estimate() > _AUTOCOMPACT_TOKENS:
        console.print(f"[yellow]⚠ Context is large (~{context.token_estimate():,} tokens) — auto-compacting...[/yellow]")
        try:
            context.compact(client, tracker)
        except Exception as e:
            console.print(f"[yellow]Auto-compact failed ({e}); continuing with full history.[/yellow]")

    context.append({"role": "user", "content": user_message})
    if logger:
        logger.user(user_message)

    for iteration in range(_MAX_TOOL_ITERATIONS):
        full_text, collected_tool_calls, finish_reason = _stream_turn(client, context, tracker)

        if finish_reason == "stop" or (finish_reason != "tool_calls" and not collected_tool_calls):
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

                result: str | None = None

                # Permission gate — show diff/warning and ask before proceeding
                if result is None and needs_permission(tool_name, args):
                    result = request_permission(tool_name, args)

                if result is None:
                    tool = get_tool_by_name(tool_name)
                    print_tool_use(label)
                    if tool is None:
                        result = f"Error: unknown tool '{tool_name}'"
                        print_tool_result(result, error=True)
                    else:
                        with console.status(f"[dim]{label}[/dim]", spinner="dots"):
                            try:
                                result = execute_with_timeout(tool, args)
                            except Exception as e:
                                result = f"Error executing {tool_name}: {e}"
                        result = truncate_tool_result(result)
                        print_tool_result(result, error=result.startswith("Error"))

                if logger:
                    logger.tool_result(tool_name, result)

                context.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

    # Iteration cap hit — ask the model for a final progress summary instead of
    # stopping silently.
    console.print()
    console.print(f"[yellow]Reached max tool iterations ({_MAX_TOOL_ITERATIONS}) — asking for a progress summary.[/yellow]")
    context.append({
        "role": "user",
        "content": "You hit the tool iteration limit. Do not call any more tools. "
                   "Summarize what you accomplished and what remains to be done.",
    })
    full_text, _, _ = _stream_turn(client, context, tracker)
    console.print()
    context.append({"role": "assistant", "content": full_text})
    if logger:
        logger.assistant(full_text)
