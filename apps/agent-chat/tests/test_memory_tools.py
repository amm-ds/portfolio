"""Agent-level memory: two runs, fresh context, and no notebook prompt bloat."""

from pathlib import Path

from agent_chat.agent import build_agent
from agent_chat.approvals import AutoApproval
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.memory.notebook import FileNotebook
from agent_chat.testing import FakeStep, scripted_model


def _final(text: str, *, expect: str | None = None, reject: str | None = None) -> FakeStep:
    return FakeStep(
        tool_call=("final_result", {"text": text, "citations": [], "uncertainty": "low"}),
        expect=expect,
        reject=reject,
    )


async def test_fact_recall_in_later_run_contains_only_matching_note(tmp_path: Path) -> None:
    notebook = FileNotebook(tmp_path)
    deps = ChatDeps(approvals=AutoApproval(), memory=notebook, session_id="alice")
    model = scripted_model(
        [
            FakeStep(tool_call=("remember", {"fact": "My favorite editor is Neovim."})),
            _final("I will remember that."),
            FakeStep(
                tool_call=("recall", {"query": "favorite editor"}),
                expect="favorite editor",
            ),
            _final(
                "Your favorite editor is Neovim.",
                expect="My favorite editor is Neovim.",
                reject="My unrelated shell is zsh.",
            ),
        ]
    )
    settings = Settings(embedder="hashing", memory_data_dir=tmp_path)
    agent = build_agent(model=model, settings=settings)

    await agent.run("Remember that my favorite editor is Neovim.", deps=deps)
    await notebook.remember("alice", "My unrelated shell is zsh.")
    # Deliberately no conversation=: only the persistent notebook links the runs.
    result = await agent.run("What is my favorite editor?", deps=deps)

    assert result.output.text == "Your favorite editor is Neovim."
    reopened = FileNotebook(tmp_path)
    notes = await reopened.recall("alice", "favorite editor")
    assert [note.fact for note in notes] == ["My favorite editor is Neovim."]
