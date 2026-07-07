from __future__ import annotations

from jarvis import todos
from jarvis.context import ContextManager, _lookup_price, _PRICING, build_multimodal_content, expand_file_mentions


class TestLookupPrice:
    def test_mini_not_mispriced_as_prefix(self):
        assert _lookup_price("gpt-4o-mini") == _PRICING["gpt-4o-mini"]
        assert _lookup_price("o1-mini-deploy") == _PRICING["o1-mini"]

    def test_exact_match(self):
        assert _lookup_price("gpt-4o") == _PRICING["gpt-4o"]

    def test_unknown_falls_back(self):
        assert _lookup_price("mystery-model") == (2.50, 10.00)

    def test_case_insensitive(self):
        assert _lookup_price("GPT-4O-MINI") == _PRICING["gpt-4o-mini"]


class TestLoadHistory:
    def test_replaces_existing_history(self):
        ctx = ContextManager()
        ctx.append({"role": "user", "content": "old"})
        ctx.load_history([{"role": "user", "content": "restored"}])
        assert ctx._history == [{"role": "user", "content": "restored"}]


class TestCleanHistory:
    def _ctx(self, history):
        ctx = ContextManager()
        for m in history:
            ctx.append(m)
        return ctx

    def test_orphaned_tool_call_dropped(self):
        ctx = self._ctx([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]},
            # no matching tool result
        ])
        cleaned = ctx._clean_history()
        assert all(not m.get("tool_calls") for m in cleaned)

    def test_orphaned_tool_result_dropped(self):
        ctx = self._ctx([
            {"role": "tool", "tool_call_id": "call_ghost", "content": "result"},
        ])
        assert ctx._clean_history() == []

    def test_complete_pair_kept(self):
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
            {"role": "assistant", "content": "done"},
        ]
        ctx = self._ctx(history)
        assert ctx._clean_history() == history


class TestTokenEstimate:
    def test_chars_div_4(self):
        ctx = ContextManager()
        ctx.append({"role": "user", "content": "x" * 400})
        assert ctx.token_estimate() == 100

    def test_none_content_ok(self):
        ctx = ContextManager()
        ctx.append({"role": "assistant", "content": None, "tool_calls": []})
        assert ctx.token_estimate() == 0


class TestPin:
    def test_pinned_notes_appear_in_system_message(self):
        ctx = ContextManager()
        ctx.pin("Always use tabs, never spaces.")
        assert "Always use tabs, never spaces." in ctx.system_message["content"]

    def test_pinned_notes_survive_clear(self):
        ctx = ContextManager()
        ctx.pin("Remember this.")
        ctx.append({"role": "user", "content": "hi"})
        ctx.clear()
        assert ctx.pinned == ["Remember this."]
        assert "Remember this." in ctx.system_message["content"]

    def test_pinned_notes_survive_compact(self):
        ctx = ContextManager()
        ctx.pin("Remember this.")
        ctx.append({"role": "user", "content": "hi"})

        class _FakeClient:
            def complete(self, messages):
                from jarvis.client import CompleteResult
                return CompleteResult(text="summary", prompt_tokens=1, completion_tokens=1)

        ctx.compact(_FakeClient())
        assert ctx.pinned == ["Remember this."]

    def test_unpin_removes_by_index(self):
        ctx = ContextManager()
        ctx.pin("first")
        ctx.pin("second")
        assert ctx.unpin(1) is True
        assert ctx.pinned == ["second"]

    def test_unpin_out_of_range_returns_false(self):
        ctx = ContextManager()
        assert ctx.unpin(1) is False


class TestBuildMultimodalContent:
    def test_plain_text_unchanged(self):
        assert build_multimodal_content("just some text") == "just some text"

    def test_nonexistent_image_path_left_as_text(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert build_multimodal_content("look at missing.png") == "look at missing.png"

    def test_existing_image_path_becomes_content_parts(self, tmp_path):
        image = tmp_path / "screenshot.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfakepngdata")

        result = build_multimodal_content(f"what is in {image}?")

        assert isinstance(result, list)
        assert result[0] == {"type": "text", "text": f"what is in {image}?"}
        assert result[1]["type"] == "image_url"
        assert result[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_jpg_extension_maps_to_jpeg_mime(self, tmp_path):
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"fakejpegdata")

        result = build_multimodal_content(str(image))

        assert result[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


class TestExpandFileMentions:
    def test_existing_file_mention_inlines_content(self, tmp_path):
        notes = tmp_path / "notes.txt"
        notes.write_text("hello world")

        result = expand_file_mentions(f"summarize @{notes} please")

        assert "[File:" in result
        assert "hello world" in result

    def test_missing_file_mention_returns_text_unchanged(self):
        text = "summarize @missing.txt please"
        assert expand_file_mentions(text) == text

    def test_image_mention_left_unchanged_for_vision_path(self, tmp_path):
        image = tmp_path / "shot.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfakepngdata")
        text = f"what is in @{image}?"

        assert expand_file_mentions(text) == text


class TestTodosInSystemMessage:
    def teardown_method(self):
        todos.clear_todos()

    def test_no_todos_section_when_empty(self):
        todos.clear_todos()
        ctx = ContextManager()
        assert "## Current Todos" not in ctx.system_message["content"]

    def test_todos_section_lists_pending_item(self):
        todos.set_todos([{"content": "ship it", "status": "pending"}])
        ctx = ContextManager()
        content = ctx.system_message["content"]
        assert "## Current Todos" in content
        assert "- [ ] ship it" in content
