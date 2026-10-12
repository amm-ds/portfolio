"""Corpus preparation: a bounded, reproducible slice of English Wikipedia.

Streams ``wikimedia/wikipedia`` (config ``20231101.en``) and selects up to
``articles_per_topic`` articles per fixed topic by case-insensitive title
matching. Article ids are deterministic (topic slug + per-topic sequence), so
re-running with the same config yields the same corpus. Quality gates run as
data (DQReport) and halt the pipeline loudly on failure.

License note: Wikipedia text is CC BY-SA 3.0 / GFDL (see README attribution).
"""

import json
import re
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any, cast

from portfolio_core.dq import DQReport
from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract

from rag_agent.config import RAGConfig
from rag_agent.schemas import Article

logger = get_logger(__name__)

HF_DATASET = "wikimedia/wikipedia"
HF_CONFIG = "20231101.en"
DATASET_SOURCE = f"https://huggingface.co/datasets/{HF_DATASET} (config {HF_CONFIG})"
WIKIPEDIA_LICENSE = "CC BY-SA 3.0 | GFDL"
SNAPSHOT_DATE = date(2023, 11, 1)  # the Wikipedia dump snapshot, not the download day

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Deterministic lowercase slug used as the article-id prefix per topic."""
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def load_corpus(config: RAGConfig) -> list[Article]:
    """Read the prepared corpus from ``config.corpus_path``."""
    path = config.corpus_path
    if not path.exists():
        raise FileNotFoundError(
            f"corpus not found at {path}. Run `python -m rag_agent.cli prepare-corpus` first."
        )
    with path.open(encoding="utf-8") as fh:
        return [Article.model_validate_json(line) for line in fh if line.strip()]


def match_topic(title: str, config: RAGConfig) -> str | None:
    """Return the topic whose title patterns match ``title`` (first match wins)."""
    lowered = title.lower()
    for topic in config.topics:
        if any(p in lowered for p in config.title_patterns(topic)):
            return topic
    return None


def _stream_rows(config: RAGConfig) -> Iterable[dict[str, Any]]:
    from datasets import load_dataset  # type: ignore[import-untyped]

    return cast(
        Iterable[dict[str, Any]],
        load_dataset(HF_DATASET, HF_CONFIG, split="train", streaming=True),
    )


def prepare_corpus(config: RAGConfig) -> DatasetContract:
    """Build ``data/raw/corpus.jsonl`` + dataset contract from the HF stream.

    Scans at most ``config.max_scan_rows`` articles and stops early once every
    topic quota is filled. Topics that remain under quota are logged, not
    silently padded — "up to N per topic" is explicit.
    """
    rows = _stream_rows(config)
    counts = {topic: 0 for topic in config.topics}
    seen_titles: set[str] = set()
    articles: list[Article] = []

    # Exact-title anchors: collected regardless of the pattern quota so the
    # flagship articles are always in the corpus when the dump contains them.
    anchor_lookup = {
        title.lower(): topic for topic, anchors in config.anchor_titles.items() for title in anchors
    }
    anchors_missing = set(anchor_lookup)

    scanned = 0
    for scanned, row in enumerate(rows, start=1):
        if scanned > config.max_scan_rows:
            scanned -= 1
            break
        title = str(row["title"]).strip()
        if not title or title in seen_titles:
            continue
        anchor_topic = anchor_lookup.get(title.lower())
        if anchor_topic is not None:
            anchors_missing.discard(title.lower())
            text = str(row["text"]).strip()[: config.max_article_chars]
            if len(text) >= 200:
                seen_titles.add(title)
                articles.append(
                    Article(
                        article_id=f"{slugify(anchor_topic)}-{counts[anchor_topic]:03d}",
                        title=title,
                        topic=anchor_topic,
                        text=text,
                    )
                )
                counts[anchor_topic] += 1
            continue
        topic = match_topic(title, config)
        if topic is None or counts[topic] >= config.articles_per_topic:
            continue
        text = str(row["text"]).strip()[: config.max_article_chars]
        if len(text) < 200:
            continue
        seen_titles.add(title)
        article = Article(
            article_id=f"{slugify(topic)}-{counts[topic]:03d}",
            title=title,
            topic=topic,
            text=text,
        )
        articles.append(article)
        counts[topic] += 1
        if scanned % 50_000 == 0:
            logger.info("scanned %d rows; collected=%s", scanned, counts)
        quotas_full = all(counts[t] >= config.articles_per_topic for t in config.topics)
        if quotas_full and not anchors_missing:
            break

    logger.info(
        "scan complete: scanned=%d collected=%d per_topic=%s", scanned, len(articles), counts
    )
    for topic, n in counts.items():
        if n < config.articles_per_topic:
            logger.warning(
                "topic %r under quota: %d of %d (raise max_scan_rows to collect more)",
                topic,
                n,
                config.articles_per_topic,
            )
    if anchors_missing:
        logger.warning("anchor titles not present in the dump: %s", sorted(anchors_missing))

    _run_gates(articles, config)
    contract = _write_artifacts(articles, config)
    logger.info("corpus written: %s (%d articles)", config.corpus_path, contract.n_rows)
    return contract


def _run_gates(articles: list[Article], config: RAGConfig) -> None:
    dq = DQReport(dataset="wikipedia-topical-corpus", n_rows=len(articles))
    n = max(len(articles), 1)
    null_title = sum(1 for a in articles if not a.title) / n
    null_text = sum(1 for a in articles if not a.text) / n
    dq.check_null_rate("title", null_title, 0.0)
    dq.check_null_rate("text", null_text, 0.0)
    if articles:
        lengths = [len(a.text) for a in articles]
        dq.check_range("text_len", min(lengths), max(lengths), 200, config.max_article_chars)
    dq.check_range("articles_total", len(articles), len(articles), 1, 10_000)
    dq.raise_if_failed()


def _write_artifacts(articles: list[Article], config: RAGConfig) -> DatasetContract:
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    contract = DatasetContract(
        name="wikipedia-topical-corpus",
        source=DATASET_SOURCE,
        license=WIKIPEDIA_LICENSE,
        snapshot_date=SNAPSHOT_DATE,
        checksum_sha256=sha256_of(config.corpus_path),
        n_rows=len(articles),
    )
    config.contract_path.parent.mkdir(parents=True, exist_ok=True)
    Path(config.contract_path).write_text(
        json.dumps(contract.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    return contract
