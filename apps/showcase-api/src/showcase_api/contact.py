"""Contact phone gate.

The direct phone line never ships in the frontend bundle; the page reveals
it only after this one deliberate step. CONTACT_PHONE is set per deployment.

Every submission (valid or not) is appended to CONTACT_STORE_PATH as one
JSON line — timestamp, validity, kind, value — so the operator can review
who asked for the line. Storage is best-effort: an unwritable or unset path
logs a warning and never fails the request.
"""

import json
import logging
import os
import re
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CONTACT_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,18}[0-9]$")

router = APIRouter()


class ContactUnlockRequest(BaseModel):
    """What the visitor shares to reveal the phone line: an email address or a
    phone number. Validated for shape; recorded in the contact store."""

    value: str = Field(min_length=3, max_length=120)


def _record_submission(value: str, valid: bool) -> None:
    """Append one JSON line to the contact store; never raise."""
    path = os.environ.get("CONTACT_STORE_PATH", "").strip()
    if not path:
        return
    if _CONTACT_EMAIL_RE.match(value):
        kind = "email"
    elif _CONTACT_PHONE_RE.match(value):
        kind = "phone"
    else:
        kind = "other"
    line = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "valid": valid,
        "kind": kind,
        "value": value[:120],
    }
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("contact store not writable (%s): %s", path, exc)


@router.post("/contact/unlock")
def unlock_contact_phone(body: ContactUnlockRequest) -> dict[str, str]:
    """Return the phone number once the visitor shares a valid email or phone
    number. Keeps the number out of page source and bundles without pretending
    to be a security boundary — any deliberate caller receives it."""
    value = body.value.strip()
    valid = bool(_CONTACT_EMAIL_RE.match(value) or _CONTACT_PHONE_RE.match(value))
    _record_submission(value, valid)
    if not valid:
        raise HTTPException(status_code=422, detail="enter a valid email address or phone number")
    # The direct line comes from the deployment's environment; empty when
    # unset so the endpoint fails closed.
    phone = os.environ.get("CONTACT_PHONE", "").strip()
    if not phone:
        raise HTTPException(
            status_code=503,
            detail="the phone line is not configured on this deployment",
        )
    return {"phone": phone}
