"""Shared pytest setup for the showcase API suite.

Interactive API docs (``/docs``, ``/redoc``, ``/openapi.json``) are env-gated
and off by default (``ENABLE_API_DOCS`` fails closed like ``RAG_CHAT_ENABLED``).
The suite asserts the docs routes and the committed OpenAPI golden, so enable
them here — conftest runs before test modules import ``showcase_api.main``.
"""

import os

os.environ.setdefault("ENABLE_API_DOCS", "1")
