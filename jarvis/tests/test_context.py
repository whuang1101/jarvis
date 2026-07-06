from __future__ import annotations

from jarvis.context import ContextManager, _lookup_price, _PRICING


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
