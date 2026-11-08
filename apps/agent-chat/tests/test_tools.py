"""Unit tests for the example tools and the tool contract."""

import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.tools import RunContext

from agent_chat.approvals import AutoApproval, DenyAll
from agent_chat.deps import ChatDeps
from agent_chat.tools.base import validate_tool
from agent_chat.tools.calculator import calculator
from agent_chat.tools.clock import clock
from agent_chat.tools.fetch_url import fetch_url
from agent_chat.tools.send_message import send_message


class TestCalculator:
    def test_basic_arithmetic(self) -> None:
        assert calculator("2 + 2") == 4.0
        assert calculator("(128 + 872) / 4") == 250.0
        assert calculator("10 % 3") == 1.0
        assert calculator("2 ** 10") == 1024.0

    def test_rounding(self) -> None:
        assert calculator("1 / 3") == round(1 / 3, 6)

    @pytest.mark.parametrize(
        "expr",
        ["two + 2", "sum([1, 2])", "__import__('os')", "2 +"],
    )
    def test_rejected_input_raises_model_retry(self, expr: str) -> None:
        """Bad input re-asks the model (ModelRetry), never executes or crashes."""
        with pytest.raises(ModelRetry):
            calculator(expr)

    def test_huge_exponent_is_a_retry_not_a_hang(self) -> None:
        with pytest.raises(ModelRetry):
            calculator("2 ** 100000")


class TestClock:
    def test_utc_default(self) -> None:
        stamp = clock()
        assert stamp.endswith("+00:00") or stamp.endswith("Z")

    def test_named_timezone(self) -> None:
        stamp = clock("Asia/Tokyo")
        assert "+09:00" in stamp

    def test_unknown_timezone_is_a_clean_error(self) -> None:
        with pytest.raises(ValueError, match="unknown timezone"):
            clock("Not/AZone")


class TestFetchUrl:
    async def test_scheme_guard(self) -> None:
        with pytest.raises(ValueError, match="http"):
            await fetch_url("file:///etc/passwd")

    async def test_title_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        mod = importlib.import_module("agent_chat.tools.fetch_url")
        monkeypatch.setattr(mod, "_read_title", lambda url: "Example Domain")
        page = await fetch_url("https://example.com")
        assert page.title == "Example Domain"
        assert page.url == "https://example.com"

    async def test_private_address_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="private and reserved addresses"):
            await fetch_url("http://127.0.0.1/admin")


class TestSendMessageGate:
    def _ctx(self, deps: ChatDeps) -> RunContext[ChatDeps]:
        from pydantic_ai.usage import RunUsage

        from agent_chat.testing import scripted_model

        return RunContext(deps=deps, model=scripted_model([]), usage=RunUsage())

    async def test_approved_posts(self) -> None:
        deps = ChatDeps(approvals=AutoApproval())
        result = await send_message(self._ctx(deps), "ops", "hi")
        assert "sent" in result
        assert deps.sent[0].channel == "ops"

    async def test_denied_never_posts(self) -> None:
        deps = ChatDeps(approvals=DenyAll())
        result = await send_message(self._ctx(deps), "ops", "hi")
        assert "NOT sent" in result
        assert deps.sent == []


class TestToolContract:
    def test_validate_tool_rejects_missing_docstring(self) -> None:
        def no_docs() -> None: ...

        with pytest.raises(ValueError, match="docstring"):
            validate_tool(no_docs)

    def test_validate_tool_rejects_private_names(self) -> None:
        def _hidden() -> None:
            """Docs."""

        with pytest.raises(ValueError, match="private"):
            validate_tool(_hidden)

    def test_validate_tool_accepts_examples(self) -> None:
        validate_tool(calculator)
        validate_tool(clock)
