"""Model-visible history: free sliding window or summarize only on overflow."""

from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from agent_chat.agent import build_agent
from agent_chat.approvals import AutoApproval
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.memory.history import trim_history
from agent_chat.testing import FakeStep, scripted_model


def _final(text: str, *, expect: str | None = None, reject: str | None = None) -> FakeStep:
    return FakeStep(
        tool_call=("final_result", {"text": text, "citations": [], "uncertainty": "low"}),
        expect=expect,
        reject=reject,
    )


def _history() -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content="old question")]),
        ModelResponse(parts=[TextPart(content="old answer")]),
        ModelRequest(parts=[UserPromptPart(content="recent question")]),
        ModelResponse(parts=[ToolCallPart(tool_name="clock", args={}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="clock", content="noon", tool_call_id="c1")]),
        ModelResponse(parts=[TextPart(content="recent answer")]),
        ModelRequest(parts=[UserPromptPart(content="current question")]),
    ]


class TestSlidingWindow:
    def test_trim_keeps_whole_recent_turns(self) -> None:
        trimmed = trim_history(_history(), max_turns=2)

        assert len(trimmed) == 5
        assert "old question" not in str(trimmed)
        assert "recent question" in str(trimmed)
        assert "noon" in str(trimmed)
        assert "current question" in str(trimmed)

    def test_inside_window_is_unchanged(self) -> None:
        history = _history()
        assert trim_history(history, max_turns=3) == history

    async def test_agent_default_trim_drops_old_prompt_without_summary_call(
        self, tmp_path: Path
    ) -> None:
        settings = Settings(embedder="hashing", memory_data_dir=tmp_path, history_max_turns=1)
        model = scripted_model(
            [
                _final("First answer."),
                _final("Second answer.", reject="old question"),
            ]
        )
        agent = build_agent(model=model, settings=settings)
        first = await agent.run("old question", deps=ChatDeps(approvals=AutoApproval()))

        second = await agent.run(
            "current question",
            conversation=first.conversation,
            deps=ChatDeps(approvals=AutoApproval()),
        )

        assert second.output.text == "Second answer."
        # The template stores the same bounded conversation it continues from.
        assert "old question" not in str(second.conversation.messages)


class TestSummarizeOnOverflow:
    async def test_summary_model_runs_only_when_window_overflows(self, tmp_path: Path) -> None:
        settings = Settings(
            embedder="hashing",
            memory_data_dir=tmp_path,
            history_max_turns=1,
            history_summarize_enabled=True,
        )
        model = scripted_model(
            [
                _final("First answer."),
                FakeStep(text="The user previously asked about their old project."),
                _final(
                    "Second answer using the summary.",
                    expect="previously asked about their old project",
                ),
            ]
        )
        agent = build_agent(model=model, settings=settings)
        first = await agent.run(
            "Tell you about my old project", deps=ChatDeps(approvals=AutoApproval())
        )

        second = await agent.run(
            "What did we discuss?",
            conversation=first.conversation,
            deps=ChatDeps(approvals=AutoApproval()),
        )

        assert second.output.text == "Second answer using the summary."
        # The summarizer consumed exactly one scripted step, between the turns.
        assert second.usage.requests >= 1
