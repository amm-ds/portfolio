"""Anonymous browser-session identity for public demo isolation.

The random session header separates notebook, conversation, and approval state;
it is not an authenticated principal or an authorization boundary.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status


def require_session_id(
    session_id: Annotated[str | None, Header(alias="x-agent-chat-session")] = None,
) -> str:
    """Require one canonical UUID supplied by the browser session helper."""
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing X-Agent-Chat-Session header",
        )
    try:
        parsed = UUID(session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Agent-Chat-Session must be a canonical UUID",
        ) from exc
    if str(parsed) != session_id.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Agent-Chat-Session must be a canonical UUID",
        )
    return str(parsed)
