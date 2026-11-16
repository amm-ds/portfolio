"""fetch_url: read a web page's title. Network only when explicitly enabled.

Every redirect hop is resolved and validated independently. The socket connects
to the validated address rather than resolving the host again, closing the DNS
check/use gap. Downloads are capped and run in a worker thread.
"""

import asyncio
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import ParseResult, urljoin, urlparse

from pydantic import BaseModel, Field

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_MAX_BYTES = 200_000  # titles live in the first chunk of the document
_MAX_REDIRECTS = 5
_TIMEOUT_S = 10.0
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class FetchedPage(BaseModel):
    """What fetch_url returns: the page title, nothing more."""

    url: str
    title: str = Field(min_length=1)
    fetched_at: str  # ISO 8601 UTC


def _public_target(url: str) -> tuple[ParseResult, int, list[str]]:
    """Validate one URL hop and return its port and public resolved addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only http(s) URLs are supported")
    if parsed.username or parsed.password:
        raise ValueError("URLs with credentials are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve {parsed.hostname}") from exc
    if not addresses:
        raise ValueError(f"could not resolve {parsed.hostname}")
    resolved = [str(address_info[4][0]) for address_info in addresses]
    for address in resolved:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("private and reserved addresses are not allowed")
    return parsed, port, resolved


def _validate_public_url(url: str) -> None:
    """Compatibility helper for callers that only need URL validation."""
    _public_target(url)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection that cannot re-resolve the validated hostname."""

    def __init__(self, host: str, *, port: int, pinned_ip: str) -> None:
        super().__init__(host, port=port, timeout=_TIMEOUT_S)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout, None)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to a pinned IP, retaining the hostname for SNI/certificates."""

    def __init__(self, host: str, *, port: int, pinned_ip: str) -> None:
        super().__init__(host, port=port, timeout=_TIMEOUT_S)
        self._pinned_ip = pinned_ip
        self._tls_context = ssl.create_default_context()

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout, None)
        self.sock = self._tls_context.wrap_socket(sock, server_hostname=self.host)


def _read_title(url: str) -> str:
    current_url = url
    for _ in range(_MAX_REDIRECTS + 1):
        parsed, port, addresses = _public_target(current_url)
        host = parsed.hostname
        if host is None:  # unreachable after _public_target; keeps the type explicit
            raise ValueError("only http(s) URLs are supported")
        connection_type = (
            _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        )
        connection = connection_type(host, port=port, pinned_ip=addresses[0])
        target = parsed.path or "/"
        if parsed.query:
            target += f"?{parsed.query}"
        try:
            connection.request("GET", target, headers={"User-Agent": "agent-chat/0.1 (+template)"})
            response = connection.getresponse()
            if response.status in _REDIRECT_STATUSES:
                location = response.getheader("Location")
                if not location:
                    raise ValueError(f"redirect from {current_url} has no Location header")
                current_url = urljoin(current_url, location)
                continue
            if not 200 <= response.status < 300:
                raise ValueError(f"could not fetch {current_url}: HTTP {response.status}")
            raw = response.read(_MAX_BYTES)
        except (OSError, http.client.HTTPException) as exc:
            raise ValueError(f"could not fetch {current_url}: {exc}") from exc
        finally:
            connection.close()
        break
    else:
        raise ValueError(f"too many redirects fetching {url}")

    match = _TITLE_RE.search(raw.decode("utf-8", errors="replace"))
    if match is None:
        raise ValueError(f"page {current_url} has no <title> element")
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
