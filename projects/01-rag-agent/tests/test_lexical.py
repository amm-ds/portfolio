"""Lexical (word-match) baseline: the fair naive floor between chance and embeddings."""

import numpy as np
from rag_agent.config import RAGConfig
from rag_agent.evaluate import first_relevant_rank, random_ranks
from rag_agent.index import ChunkRecord, Retriever, build_index
from rag_agent.lexical import lexical_ranks, tokenize
from rag_agent.schemas import EvalQuestion


def _chunk(chunk_id: str, article_id: str, text: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        article_id=article_id,
        text=text,
        token_count=len(text.split()),
        title=article_id,
        topic="test",
    )


def _fixture() -> tuple[list[ChunkRecord], list[EvalQuestion]]:
    """Toy corpus: one relevant chunk per question + wordy + filler distractors."""
    chunks = [
        _chunk("c1", "art-a", "The greenhouse effect warms the planet surface"),
        _chunk("c2", "art-b", "Solar panels convert sunlight into electricity"),
        _chunk("c3", "art-c", "Photosynthesis converts light into chemical energy"),
        _chunk("c4", "art-d", "The history of aviation spans two centuries"),
        _chunk("c5", "art-e", "Wikipedia is a free online encyclopedia"),
    ]
    # Unrelated filler: enough volume that a random shuffle rarely lands a
    # relevant chunk in the top-5 (chance floor well below word-match).
    chunks += [
        _chunk(f"f{i}", f"filler-{i:02d}", f"Filler article number {i} about gardening tools")
        for i in range(40)
    ]
    questions = [
        EvalQuestion(
            question="How does the greenhouse effect warm the planet?",
            relevant_article_ids=["art-a"],
        ),
        EvalQuestion(
            question="What converts sunlight into electricity?",
            relevant_article_ids=["art-b"],
        ),
        EvalQuestion(question="What is photosynthesis?", relevant_article_ids=["art-c"]),
    ]
    return chunks, questions


def test_tokenize_lowercases_strips_stopwords() -> None:
    assert tokenize("The Greenhouse, EFFECT!") == ["greenhouse", "effect"]
    assert tokenize("What is the?") == []  # stopwords and punctuation only


def _recall5(ranks: list[int | None]) -> float:
    return sum(1 for r in ranks if r is not None and r <= 5) / len(ranks)


def test_lexical_beats_random_and_is_deterministic() -> None:
    chunks, questions = _fixture()
    first = lexical_ranks(chunks, questions)
    assert first == lexical_ranks(chunks, questions)  # deterministic
    assert _recall5(first) > _recall5(random_ranks(RAGConfig(), questions, chunks))
    assert _recall5(first) == 1.0  # every toy question is word-matchable


def test_lexical_loses_to_embeddings_on_paraphrase(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Word-match misses a paraphrase; a semantics-aware ranker finds it."""
    chunks, _ = _fixture()
    config = RAGConfig()

    # Topic one-hot embedder: each chunk/query vector peaks on its topic slot
    # (the aviation slot also matches the paraphrase "planes"), so paraphrased
    # wording still retrieves the right article.
    topics = ["greenhouse", "solar", "photosynthesis", "aviation", "encyclopedia"]
    synonyms = {"aviation": ("aviation", "planes", "aircraft")}

    def embed_fn(texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), len(topics)), dtype=np.float32)
        for i, text in enumerate(texts):
            lowered = text.lower()
            for j, topic in enumerate(topics):
                if any(word in lowered for word in synonyms.get(topic, (topic,))):
                    vecs[i, j] = 1.0
        return vecs

    build_index(chunks, embed_fn, tmp_path)
    retriever = Retriever.from_index_dir(config, tmp_path, embed_fn)

    paraphrase = EvalQuestion(question="how do planes fly", relevant_article_ids=["art-d"])
    lex = lexical_ranks(chunks, [paraphrase])[0]
    assert lex is None or lex > 5  # no content-word overlap with the aviation chunk
    emb = first_relevant_rank(
        retriever.search(paraphrase.question, top_k=5), paraphrase.relevant_article_ids
    )
    assert emb == 1  # embeddings found what word-match could not
