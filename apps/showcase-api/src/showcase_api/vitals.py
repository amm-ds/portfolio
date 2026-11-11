"""Privacy-preserving field Web Vitals collection (external evaluation P1-5).

The SPA reports p75-bound measurements (LCP, INP, CLS) with the route, the
device class and the release build SHA. Nothing else: no cookies, no client
identifiers, no message content, no full URLs — the route is reduced to its
first two path segments before it leaves the browser. The endpoint validates
with pydantic, appends to a JSONL file (retention: last 50k entries / 30 days,
whichever is smaller), and answers 204. Same-origin only, so the strict CSP's
connect-src 'self' covers it with no policy change.
"""

import json
import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from portfolio_core.logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger("showcase_api.vitals")

router = APIRouter()

_RETENTION_MAX_ENTRIES = 50_000
_RETENTION_DAYS = 30


class Vital(BaseModel):
    metric: str = Field(pattern="^(LCP|INP|CLS)$")
    value: float = Field(ge=0, le=1_000_000)
    route: str = Field(min_length=1, max_length=120)
    device: str = Field(pattern="^(mobile|tablet|desktop)$")
    sha: str = Field(min_length=3, max_length=64)


class VitalBatch(BaseModel):
    vitals: list[Vital] = Field(min_length=1, max_length=20)


def _vitals_path() -> Path | None:
    """Configured store path, or None (collection becomes a no-op with one
    warning — no hardcoded temp paths)."""
    raw = os.environ.get("VITALS_PATH")
    return Path(raw) if raw else None


_lock = threading.Lock()
_state = {"warned_unconfigured": False}


def _trim(path: Path) -> None:
    """Bound the file: newest _RETENTION_MAX_ENTRIES lines, ≤ 30 days old."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    cutoff = time.time() - _RETENTION_DAYS * 86400
    kept = [ln for ln in lines[-_RETENTION_MAX_ENTRIES:]]
    out: list[str] = []
    for ln in kept:
        try:
            if json.loads(ln).get("ts", 0) >= cutoff:
                out.append(ln)
        except (ValueError, AttributeError):
            out.append(ln)  # malformed lines are not our data to judge
    if len(out) != len(lines):
        path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")


@router.post("/vitals", include_in_schema=False)
async def collect_vitals(request: Request) -> Response:
    """Append one batch of field vitals; 204 on success, 422 on bad payload."""
    try:
        batch = VitalBatch.model_validate(await request.json())
    except Exception:
        return JSONResponse({"error": "invalid vitals payload"}, status_code=422)

    path = _vitals_path()
    if path is None:
        if not _state["warned_unconfigured"]:
            _state["warned_unconfigured"] = True
            logger.warning("vitals: VITALS_PATH unset; field measurements are dropped")
        return Response(status_code=204)

    now = time.time()
    with _lock:
        try:
            with path.open("a", encoding="utf-8") as fh:
                for vital in batch.vitals:
                    fh.write(
                        json.dumps(
                            {
                                "ts": now,
                                "metric": vital.metric,
                                "value": round(vital.value, 4),
                                "route": vital.route,
                                "device": vital.device,
                                "sha": vital.sha,
                            },
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            if path.stat().st_size > 8_000_000:
                _trim(path)
        except OSError as e:
            logger.warning("vitals: could not persist (%s)", e)
    return Response(status_code=204)
