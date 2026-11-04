"""Contact phone gate.

The direct phone line never ships in the frontend bundle; the page reveals
it only after this one deliberate step. CONTACT_PHONE is set per deployment.
"""

import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CONTACT_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,18}[0-9]$")

router = APIRouter()


class ContactUnlockRequest(BaseModel):
    """What the visitor shares to reveal the phone line: an email address or a
    phone number. Validated for shape only — the value is never stored."""

    value: str = Field(min_length=3, max_length=120)


@router.post("/contact/unlock")
def unlock_contact_phone(body: ContactUnlockRequest) -> dict[str, str]:
    """Return the phone number once the visitor shares a valid email or phone
    number. Keeps the number out of page source and bundles without pretending
    to be a security boundary — any deliberate caller receives it."""
    value = body.value.strip()
    if not (_CONTACT_EMAIL_RE.match(value) or _CONTACT_PHONE_RE.match(value)):
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
