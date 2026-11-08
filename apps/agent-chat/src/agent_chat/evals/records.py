"""The output type of one graded eval run."""

from pydantic import BaseModel

from agent_chat.schemas import Citation, SentMessage


class EvalRunRecord(BaseModel):
    """What one graded run produced — the output type of the dataset."""

    name: str
    prompt: str
    kind: str
    answer: str
    citations: list[Citation]
    tools_used: list[str]
    evidence: list[str] = []
    sent: list[SentMessage] = []
    error: str | None = None
