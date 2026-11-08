"""Authenticated gateway identity and an explicitly development-only alternative."""

import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from pydantic import Field

from document_intelligence.domain.base import StrictModel


class Principal(StrictModel):
    tenant_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    actor_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$")


async def authenticate(
    request: Request,
    x_dev_tenant: Annotated[str | None, Header(alias="X-Dev-Tenant")] = None,
    x_dev_actor: Annotated[str | None, Header(alias="X-Dev-Actor")] = None,
    x_gateway_tenant: Annotated[str | None, Header(alias="X-Gateway-Tenant")] = None,
    x_gateway_actor: Annotated[str | None, Header(alias="X-Gateway-Actor")] = None,
    x_gateway_timestamp: Annotated[str | None, Header(alias="X-Gateway-Timestamp")] = None,
    x_gateway_signature: Annotated[str | None, Header(alias="X-Gateway-Signature")] = None,
) -> Principal:
    """Verify gateway HMAC; never trust an unsigned tenant header in production.

    Development identity is available only when both ``identity_mode=development``
    and ``environment`` is not ``production``. It is for local UI work and tests.
    """
    settings = request.app.state.app_state.settings
    if settings.identity_mode == "development":
        if settings.environment == "production":
            raise HTTPException(status_code=500, detail="Development identity is disabled")
        if not x_dev_tenant or not x_dev_actor:
            raise HTTPException(status_code=401, detail="Missing development identity")
        return Principal(tenant_id=x_dev_tenant, actor_id=x_dev_actor)
    secret = settings.gateway_shared_secret.get_secret_value()
    if not secret:
        raise HTTPException(status_code=500, detail="Gateway authentication is not configured")
    if not all([x_gateway_tenant, x_gateway_actor, x_gateway_timestamp, x_gateway_signature]):
        raise HTTPException(status_code=401, detail="Missing authenticated gateway identity")
    try:
        timestamp = int(x_gateway_timestamp or "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid gateway timestamp") from exc
    if abs(int(time.time()) - timestamp) > settings.gateway_max_skew_seconds:
        raise HTTPException(status_code=401, detail="Expired gateway identity")
    message = "\n".join(["v1", str(timestamp), x_gateway_tenant or "", x_gateway_actor or ""])
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_gateway_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid gateway signature")
    return Principal(tenant_id=x_gateway_tenant or "", actor_id=x_gateway_actor or "")


Identity = Annotated[Principal, Depends(authenticate)]
