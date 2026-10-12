"""Stdlib logging configured once, imported everywhere (playbook §Logging)."""

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Idempotent root-logger configuration."""
    global _CONFIGURED
    root = logging.getLogger()
    if _CONFIGURED and root.level == logging.getLevelName(level):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s :: %(message)s", "%H:%M:%S")
    )
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
