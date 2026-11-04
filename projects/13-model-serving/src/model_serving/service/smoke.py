"""One-shot smoke client for the container (compose smoke + `docker run`).

Stdlib urllib only — the runtime image has no httpx guarantee beyond the
installed venv, and a smoke check should carry zero dependencies of its own.
Hits /health, /ready and /predict with a legal all-zeros row, prints the
prediction on the ``SMOKE prediction:`` line the docker stage greps for, and
exits nonzero on any failure.
"""

import json
import os
import sys
import urllib.request
from urllib.response import addinfourl

SMOKE_ROW: dict[str, object] = {
    "hour": 0,
    "temp": 0.5,
    "hum": 0.5,
    "windspeed": 0.1,
    "weathersit": 1,
    "hour_sin": 0.0,
    "hour_cos": 1.0,
    "weekday_sin": 0.0,
    "weekday_cos": 1.0,
    "month_sin": 0.0,
    "month_cos": 1.0,
    "holiday": 0,
    "workingday": 0,
    "cnt_lag_1h": 100.0,
    "cnt_lag_24h": 120.0,
    "cnt_lag_168h": 110.0,
}


def _open(url: str) -> addinfourl:
    """http(s)-only urlopen — the smoke target is the service, never a file."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"SMOKE_URL must be http(s), got {url!r}")
    response: addinfourl = urllib.request.urlopen(url, timeout=5)  # noqa: S310
    return response


def _post(req: urllib.request.Request) -> addinfourl:
    response: addinfourl = urllib.request.urlopen(req, timeout=10)  # noqa: S310
    return response


def main() -> int:
    base = os.environ.get("SMOKE_URL", "http://127.0.0.1:8000").rstrip("/")
    for path in ("/health", "/ready"):
        with _open(f"{base}{path}") as r:
            if r.status != 200:
                print(f"SMOKE fail: {path} -> {r.status}", file=sys.stderr)
                return 1
    req = urllib.request.Request(  # noqa: S310 - url scheme guarded in _open/_post
        f"{base}/predict",
        data=json.dumps({"row": SMOKE_ROW}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _post(req) as r:
        if r.status != 200:
            print(f"SMOKE fail: /predict -> {r.status}", file=sys.stderr)
            return 1
        prediction = json.loads(r.read())["prediction"]
    print(f"SMOKE prediction: {prediction}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
