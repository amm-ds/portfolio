"""fetch_url: read a web page's title. Network only when explicitly enabled.

The agent only receives this tool when ``Settings.fetch_url_enabled`` is true
(see ``agent_chat.agent.build_agent``) — an adopter opts into network access
deliberately. Downloads are capped and run in a worker thread so the event
loop is never blocked by the socket.
"""

import asyncio
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_MAX_BYTES = 200_000  # titles live in the first chunk of the document


class FetchedPage(BaseModel):
    """What fetch_url returns: the page title, nothing more."""

    url: str
    title: str = Field(min_length=1)
    fetched_at: str  # ISO 8601 UTC


def _read_title(url: str) -> str:
    # S310: schemes are guarded in fetch_url before this runs; the tool is opt-in.
    request = Request(url, headers={"User-Agent": "agent-chat/0.1 (+template)"})  # noqa: S310
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - opt-in tool, capped read
            raw = response.read(_MAX_BYTES)
    except URLError as exc:
        raise ValueError(f"could not fetch {url}: {exc.reason}") from exc
    match = _TITLE_RE.search(raw.decode("utf-8", errors="replace"))
    if match is None:
        raise ValueError(f"page {url} has no <title> element")
    return " ".join(match.group(1).split())


async def fetch_url(url: str) -> FetchedPage:
    """Fetch a web page and return its title.

    Network access is only available when the deployment enables it. The page
    body is never returned — only the title — and downloads are capped.

    Args:
        url: Absolute http(s) URL to fetch.

    Returns:
        The page title and fetch metadata.
    """
    from datetime import UTC, datetime

    if not url.startswith(("http://", "https://")):
        raise ValueError("only http(s) URLs are supported")
    title = await asyncio.to_thread(_read_title, url)
    return FetchedPage(
        url=url, title=title, fetched_at=datetime.now(UTC).isoformat(timespec="seconds")
    )
