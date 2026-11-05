"""Personal notebooks: durable per-user facts with bounded on-demand recall."""

from pathlib import Path

import pytest

from agent_chat.memory.notebook import FileNotebook


class TestFileNotebook:
    async def test_recall_returns_only_relevant_notes(self, tmp_path: Path) -> None:
        notebook = FileNotebook(tmp_path)
        await notebook.remember("alice", "My favorite editor is Neovim.")
        await notebook.remember("alice", "My unrelated deployment region is eu-west-1.")

        notes = await notebook.recall("alice", "What is my favorite editor?")

        assert [note.fact for note in notes] == ["My favorite editor is Neovim."]

    async def test_second_store_instance_sees_stored_note(self, tmp_path: Path) -> None:
        first_process = FileNotebook(tmp_path)
        await first_process.remember("alice", "I prefer concise status updates.")

        second_process = FileNotebook(tmp_path)
        notes = await second_process.recall("alice", "concise status")

        assert len(notes) == 1
        assert notes[0].fact == "I prefer concise status updates."
        assert second_process.path_for("alice").is_file()

    async def test_user_notebooks_are_isolated(self, tmp_path: Path) -> None:
        notebook = FileNotebook(tmp_path)
        await notebook.remember("alice", "Alice likes Neovim.")
        await notebook.remember("bob", "Bob likes Emacs.")

        assert [note.fact for note in await notebook.recall("alice", "likes")] == [
            "Alice likes Neovim."
        ]
        alice = await notebook.recall("alice", "Neovim")
        bob = await notebook.recall("bob", "Emacs")
        assert [note.fact for note in alice] == ["Alice likes Neovim."]
        assert [note.fact for note in bob] == ["Bob likes Emacs."]
        assert notebook.path_for("alice") != notebook.path_for("bob")

    async def test_exact_repeat_does_not_duplicate_note(self, tmp_path: Path) -> None:
        notebook = FileNotebook(tmp_path)
        first = await notebook.remember("alice", "Use   dark mode.")
        second = await notebook.remember("alice", "Use dark mode.")

        assert first.id == second.id
        assert len(await notebook.recall("alice", "dark")) == 1

    async def test_recall_limit_is_bounded(self, tmp_path: Path) -> None:
        notebook = FileNotebook(tmp_path)
        for index in range(4):
            await notebook.remember("alice", f"Project preference {index}: use typed interfaces.")

        notes = await notebook.recall("alice", "typed interfaces", limit=2)

        assert len(notes) == 2

    async def test_unsafe_user_id_is_rejected(self, tmp_path: Path) -> None:
        notebook = FileNotebook(tmp_path)
        for user_id in ["../alice", "alice/bob", "", "."]:
            with pytest.raises(ValueError, match="user_id"):
                await notebook.remember(user_id, "must not escape the data dir")
