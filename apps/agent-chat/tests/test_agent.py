"""The assembled agent: structured output, budgets, retries, gates, skills."""

import pytest
from pydantic_ai import UsageLimitExceeded

from agent_chat.agent import build_agent, build_usage_limits
from agent_chat.approvals import AutoApproval, DenyAll
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.testing import FakeStep, scripted_model


def _final(text: str, uncertainty: str = "low") -> FakeStep:
    return FakeStep(
        tool_call=(
            "final_result",
            {"text": text, "citations": [], "uncertainty": uncertainty},
        )
    )


class TestAnswerFlow:
    async def test_structured_answer_with_citations(self) -> None:
        model = scripted_model(
            [
                FakeStep(
                    tool_call=(
                        "final_result",
                        {
                            "text": "The SLA is 1 hour.",
                            "citations": [{"source": "sla.md", "quote": "within 1 hour"}],
                            "uncertainty": "low",
                        },
                    )
                )
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        result = await agent.run("SLA?", deps=ChatDeps(approvals=AutoApproval()))
        assert result.output.text == "The SLA is 1 hour."
        assert result.output.citations[0].source == "sla.md"
        assert result.output.uncertainty == "low"
        assert result.usage.input_tokens > 0

    async def test_conversation_accumulates_usage(self) -> None:
        model = scripted_model([_final("one."), _final("two.")])
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        first = await agent.run("first", deps=ChatDeps(approvals=AutoApproval()))
        second = await agent.run(
            "second",
            conversation=first.conversation,
            deps=ChatDeps(approvals=AutoApproval()),
        )
        assert second.conversation.conversation_id == first.conversation.conversation_id
        assert second.usage.input_tokens >= first.usage.input_tokens


class TestToolUse:
    async def test_calculator_tool_call(self) -> None:
        model = scripted_model(
            [
                FakeStep(tool_call=("calculator", {"expr": "987 * 123"})),
                _final("987 * 123 = 121401."),
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        result = await agent.run("multiply", deps=ChatDeps(approvals=AutoApproval()))
        assert "121401" in result.output.text

    async def test_model_retry_recovers_from_bad_tool_args(self) -> None:
        """calculator raises ModelRetry on garbage; the model re-tries cleanly."""
        model = scripted_model(
            [
                FakeStep(tool_call=("calculator", {"expr": "two plus two"})),
                FakeStep(tool_call=("calculator", {"expr": "2 + 2"}), expect="parse"),
                _final("2 + 2 = 4."),
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        result = await agent.run("add", deps=ChatDeps(approvals=AutoApproval()))
        assert result.output.text == "2 + 2 = 4."


class TestUsageLimits:
    async def test_request_limit_aborts_the_run(self) -> None:
        """Three model requests against request_limit=2 → UsageLimitExceeded."""
        model = scripted_model(
            [
                FakeStep(tool_call=("calculator", {"expr": "1"})),  # request 1
                FakeStep(tool_call=("calculator", {"expr": "2"})),  # request 2
                FakeStep(tool_call=("calculator", {"expr": "3"})),  # request 3: over budget
                _final("never reached"),
            ]
        )
        settings = Settings(embedder="hashing", usage_request_limit=2)
        agent = build_agent(model=model, settings=settings)
        with pytest.raises(UsageLimitExceeded):
            await agent.run(
                "count",
                deps=ChatDeps(approvals=AutoApproval()),
                usage_limits=build_usage_limits(settings),
            )

    def test_zero_means_unlimited(self) -> None:
        limits = build_usage_limits(
            Settings(embedder="hashing", usage_request_limit=0, usage_input_tokens_limit=0)
        )
        assert limits.request_limit is None
        assert limits.input_tokens_limit is None


class TestApprovalGate:
    async def test_denied_send_message_reports_no_action(self) -> None:
        model = scripted_model(
            [
                FakeStep(tool_call=("send_message", {"channel": "ops", "text": "hi"})),
                _final("The operator declined; nothing was posted.", uncertainty="low"),
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        deps = ChatDeps(approvals=DenyAll())
        result = await agent.run("announce", deps=deps)
        assert "declined" in result.output.text
        assert deps.sent == []

    async def test_approved_send_message_records_it(self) -> None:
        model = scripted_model(
            [
                FakeStep(tool_call=("send_message", {"channel": "ops", "text": "hi"})),
                _final("Posted."),
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        deps = ChatDeps(approvals=AutoApproval())
        await agent.run("announce", deps=deps)
        assert [(s.channel, s.text) for s in deps.sent] == [("ops", "hi")]


class TestSkillsOnTheAgent:
    async def test_deferred_skill_end_to_end(self) -> None:
        model = scripted_model(
            [
                FakeStep(tool_call=("load_capability", {"capability_id": "handbook"})),
                FakeStep(tool_call=("search_handbook", {"query": "refund"}), expect="refund"),
                _final("30 days."),
            ]
        )
        agent = build_agent(model=model, settings=Settings(embedder="hashing"))
        result = await agent.run("refund window?", deps=ChatDeps(approvals=AutoApproval()))
        assert result.output.text == "30 days."
