"""API-key header stub: when ``AGENT_CHAT_API_KEY`` is set, all mutating and
chat endpoints require the matching ``X-API-Key`` header. Compared with
``hmac.compare_digest``; when the setting is empty, auth is off (the template
default — turn it on by setting a key).
"""

import hmac

from fastapi import HTTPException, Request, status


async def require_api_key(request: Request) -> None:
    """Dependency: 401 unless the presented key matches the configured one."""
    settings = request.app.state.agent_chat.settings
    if not settings.api_key:
        return
    presented = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(presented.encode(), settings.api_key.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key header",
        )
