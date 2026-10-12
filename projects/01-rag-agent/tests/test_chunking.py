"""Property-style unit tests for the paragraph-aware recursive splitter."""

import itertools

import pytest
from rag_agent.chunking import chunk_by_size


def words(text: str) -> list[str]:
    return text.split()


def test_empty_and_whitespace_text_yield_no_chunks() -> None:
    assert chunk_by_size("", "a", size=10, overlap=2) == []
    assert chunk_by_size("   \n\n  ", "a", size=10, overlap=2) == []


def test_single_short_text_is_one_chunk() -> None:
    chunks = chunk_by_size("hello world", "art-1", size=10, overlap=2)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].chunk_id == "art-1#c000"
    assert chunks[0].token_count == 2


@pytest.mark.parametrize("bad_size,bad_overlap", [(0, 0), (10, -1), (10, 10), (10, 11)])
def test_invalid_size_or_overlap_raises(bad_size: int, bad_overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_by_size("some words here", "a", size=bad_size, overlap=bad_overlap)


def test_word_window_overlap_is_exact() -> None:
    # One paragraph with no sentence boundaries is split at word windows.
    tokens = [f"w{i:02d}" for i in range(25)]
    text = " ".join(tokens)
    chunks = chunk_by_size(text, "p", size=10, overlap=3)
    assert len(chunks) == 4  # ceil((25-3)/(10-3))
    for chunk in chunks:
        assert chunk.token_count <= 10
    for prev, nxt in itertools.pairwise(chunks):
        assert words(prev.text)[-3:] == words(nxt.text)[:3]


def test_paragraphs_are_packed_whole_when_they_fit() -> None:
    paragraphs = [f"paragraph {i} " + " ".join(["filler"] * 3) for i in range(4)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_by_size(text, "p", size=12, overlap=3)
    # Each paragraph is 5 words; two fit per 12-word chunk -> 2 chunks, no splitting.
    assert len(chunks) == 2
    for chunk in chunks:
        assert chunk.token_count <= 12
        assert "paragraph" in chunk.text


def test_long_paragraph_splits_on_sentence_boundaries() -> None:
    sentences = [
        "Solar panels convert sunlight into electricity.",
        "Photons knock electrons loose in a semiconductor.",
        "This generates direct current that inverters convert.",
    ]
    paragraph = " ".join(sentences)  # 19 words, no blank lines
    chunks = chunk_by_size(paragraph, "p", size=10, overlap=2)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.token_count <= 10


def test_chunk_ids_are_deterministic() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    first = chunk_by_size(text, "x", size=5, overlap=1)
    second = chunk_by_size(text, "x", size=5, overlap=1)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.text for c in first] == [c.text for c in second]


def test_article_id_is_stamped_on_every_chunk() -> None:
    chunks = chunk_by_size("one two three four five", "art-9", size=4, overlap=1)
    assert all(c.article_id == "art-9" for c in chunks)
    assert chunks[0].chunk_id == "art-9#c000"
