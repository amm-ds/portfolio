"""Shared citation provenance parsing for production validation and evals."""

import ast
import re
from dataclasses import dataclass

from agent_chat.schemas import Citation

_RETRIEVAL_RE = re.compile(
    r"^(?P<source>.+)#(?P<chunk>\d+) \(score [^)]*\): (?P<content>.*)$",
    re.DOTALL,
)
_APOSTROPHES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u2032": "'"})


def normalize_grounding_text(text: str) -> str:
    """Normalize typography and line wrapping without changing token order."""
    return " ".join(text.translate(_APOSTROPHES).casefold().split())


@dataclass(frozen=True)
class EvidenceDocument:
    """One cited passage and the exact source/chunk that supplied it."""

    source: str
    content: str
    chunk_index: int | None = None

    @property
    def citation_source(self) -> str:
        if self.chunk_index is None:
            return self.source
        return f"{self.source}#{self.chunk_index}"


def parse_evidence(evidence: list[str]) -> list[EvidenceDocument]:
    """Parse retrieve and skill results without losing per-source boundaries."""
    documents: list[EvidenceDocument] = []
    for raw in evidence:
        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            parsed = raw
        values = parsed if isinstance(parsed, list) else [raw]
        for value in values:
            if not isinstance(value, str):
                continue
            retrieval = _RETRIEVAL_RE.match(value)
            if retrieval is not None:
                documents.append(
                    EvidenceDocument(
                        source=retrieval.group("source"),
                        chunk_index=int(retrieval.group("chunk")),
                        content=retrieval.group("content"),
                    )
                )
                continue
            source, separator, content = value.partition(" — ")
            if separator:
                documents.append(EvidenceDocument(source=source.strip(), content=content))
            else:
                documents.append(EvidenceDocument(source="retrieval", content=value))
    return documents


def citation_supported(citation: Citation, documents: list[EvidenceDocument]) -> bool:
    """A citation must quote one passage from its claimed source/chunk."""
    quote = normalize_grounding_text(citation.quote)
    return any(
        citation.source in {document.source, document.citation_source}
        and quote in normalize_grounding_text(document.content)
        for document in documents
    )
