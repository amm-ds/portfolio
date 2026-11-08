"""Canonical JSON payloads for operational audit events."""

import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Serialize an audit payload deterministically for append-only storage."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
