"""The clock tool: current time in any IANA timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def clock(timezone: str = "UTC") -> str:
    """Get the current date and time in a named timezone.

    Args:
        timezone: IANA timezone name, e.g. "UTC", "Europe/Madrid",
            "America/New_York". Defaults to UTC.

    Returns:
        ISO 8601 timestamp with offset, e.g. "2026-11-05T14:30:00+01:00".
    """
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"unknown timezone {timezone!r}; use an IANA name like 'Europe/Madrid'"
        ) from exc
    return datetime.now(tz).isoformat(timespec="seconds")
