"""send_message: the one consequential tool — it asks a human first.

Demonstrates the HITL pattern: before anything is posted, the tool goes
through ``ChatDeps.approvals``. In the API that gate emits an
``approval_request`` SSE event and waits (timeout = default deny); in evals
and scripts it is an ``AutoApproval``. The action only happens after a ``True``.
"""

from pydantic_ai.tools import RunContext

from agent_chat.deps import ChatDeps
from agent_chat.schemas import SentMessage


async def send_message(ctx: RunContext[ChatDeps], channel: str, text: str) -> str:
    """Post a message to a team channel. CONSEQUENTIAL: requires human approval.

    Use only when the user explicitly asks to notify, announce, or message a
    channel. Nothing is posted until a human approves the exact text; on
    denial or timeout the message is discarded.

    Args:
        channel: Channel name without '#', e.g. "ops" or "engineering".
        text: The exact message to post.

    Returns:
        Confirmation, or a note that the message was not sent.
    """
    summary = f"post to #{channel}: {text[:120]}"
    approved = await ctx.deps.approvals.request("send_message", summary)
    if not approved:
        return f"Message to #{channel} NOT sent: denied by operator."
    ctx.deps.sent.append(SentMessage(channel=channel, text=text))
    return f"Message sent to #{channel}."
