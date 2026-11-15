"""Contact phone gate.

The direct phone line never ships in the frontend bundle; the page reveals
it only after this one deliberate step. CONTACT_PHONE is set per deployment.

Only valid, successfully unlocked submissions are appended to
CONTACT_STORE_PATH as one JSON line — timestamp, kind, value — so the operator
can review who asked for the line. A 30-day retention window and a 1,000-entry
cap are enforced at startup, daily and on write. Legacy records, which cannot
prove a successful unlock, are dropped during migration. Storage is best-effort:
an unwritable or unset path logs a warning and never fails the request.
"""

import fcntl
import json
import logging
import os
import re
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CONTACT_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,18}[0-9]$")
_RETENTION_SECONDS = 30 * 86400
_RETENTION_MAX_ENTRIES = 1_000
_lock = threading.Lock()

router = APIRouter()


class ContactUnlockRequest(BaseModel):
    """What the visitor shares to reveal the phone line: an email address or a
    phone number. Only valid, successful unlocks are recorded."""

    value: str = Field(min_length=3, max_length=120)


def _store_path() -> Path | None:
    raw = os.environ.get("CONTACT_STORE_PATH", "").strip()
    return Path(raw) if raw else None


def _cleanup_stale_temps(path: Path) -> None:
    """Remove crash leftovers while the inter-process store lock is held."""
    for temp in path.parent.glob(f".{path.name}.tmp-*"):
        with suppress(OSError):
            temp.unlink()


@contextmanager
def _store_lock(path: Path) -> Iterator[None]:
    """Serialize API workers and operator commands on the shared volume."""
    lock_path = path.with_name(f".{path.name}.lock")
    with _lock, lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            _cleanup_stale_temps(path)
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _retained_lines(lines: list[str], now: datetime) -> list[str]:
    """Keep parseable, in-window records; malformed lines may contain personal
    data, so retention drops them rather than preserving them indefinitely."""
    kept: list[str] = []
    for line in lines[-_RETENTION_MAX_ENTRIES:]:
        try:
            record = json.loads(line)
            # Legacy records predate the successful-unlock-only policy. Even
            # valid=true cannot prove that a configured phone was returned.
            if "valid" in record:
                continue
            ts = datetime.fromisoformat(record["ts"])
            age = (now - ts).total_seconds()
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= age <= _RETENTION_SECONDS:
            kept.append(json.dumps(record, ensure_ascii=False))
    return kept


def _write_lines(path: Path, lines: list[str]) -> None:
    """Atomically replace the store so an interrupted prune cannot truncate it."""
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.tmp-", delete=False
        ) as fh:
            temp_name = fh.name
            fh.write("\n".join(lines) + ("\n" if lines else ""))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None:
            with suppress(OSError):
                Path(temp_name).unlink()


def _prune_path(path: Path, now: datetime) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    kept = _retained_lines(lines, now)
    if kept != lines:
        _write_lines(path, kept)


def prune_contact_store(now: datetime | None = None) -> None:
    """Apply the contact retention policy; safe to call at startup and daily."""
    path = _store_path()
    if path is None:
        return
    try:
        with _store_lock(path):
            _prune_path(path, now or datetime.now(UTC))
    except OSError as exc:
        logger.warning("contact store not writable (%s): %s", path, exc)


def delete_contact_submissions(value: str) -> int:
    """Delete only the exact submitted contact value; return the removal count.

    This operator-only function deliberately has no HTTP route. Errors propagate
    so the maintenance command cannot claim a deletion that failed.
    """
    target = value.strip()
    if not target:
        raise ValueError("contact value must not be empty")
    path = _store_path()
    if path is None:
        return 0
    with _store_lock(path):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return 0
        kept: list[str] = []
        removed = 0
        for line in lines:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            if str(record.get("value", "")).strip() == target:
                removed += 1
            else:
                kept.append(json.dumps(record, ensure_ascii=False))
        if removed or len(kept) != len(lines):
            _write_lines(path, kept)
        return removed


def _record_submission(value: str) -> None:
    """Append one valid unlock and apply retention; never raise."""
    path = _store_path()
    if path is None:
        return
    now = datetime.now(UTC)
    kind = "email" if _CONTACT_EMAIL_RE.match(value) else "phone"
    line = {
        "ts": now.isoformat(timespec="seconds"),
        "kind": kind,
        "value": value[:120],
    }
    try:
        with _store_lock(path):
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            _prune_path(path, now)
    except OSError as exc:
        logger.warning("contact store not writable (%s): %s", path, exc)


@router.post("/contact/unlock")
def unlock_contact_phone(body: ContactUnlockRequest) -> dict[str, str]:
    """Return the phone number once the visitor shares a valid email or phone
    number. Keeps the number out of page source and bundles without pretending
    to be a security boundary — any deliberate caller receives it."""
    value = body.value.strip()
    valid = bool(_CONTACT_EMAIL_RE.match(value) or _CONTACT_PHONE_RE.match(value))
    if not valid:
        raise HTTPException(status_code=422, detail="enter a valid email address or phone number")
    # The direct line comes from the deployment's environment; empty when
    # unset so the endpoint fails closed without collecting a contact value.
    phone = os.environ.get("CONTACT_PHONE", "").strip()
    if not phone:
        raise HTTPException(
            status_code=503,
            detail="the phone line is not configured on this deployment",
        )
    _record_submission(value)
    return {"phone": phone}
