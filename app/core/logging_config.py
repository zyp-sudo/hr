"""Centralized logging — clean, colour-coded, noise-free.

Imported as a side-effect by ``app.main`` before any route module.

Logs are written to both stdout (colour-coded) and ``logs/app.log``
(plain text, rotated at 10 MB, 5 backups kept).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure() -> None:
    """Wire up structured logging.  Idempotent across reloader restarts."""

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    # ---- formatters ---------------------------------------------------------
    _CONSOLE_FMT = (
        "\033[2m%(asctime)s\033[0m"
        "  \033[36m%(levelname)-7s\033[0m"
        "  %(message)s"
    )
    _FILE_FMT = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"

    console_fmtr = logging.Formatter(_CONSOLE_FMT, datefmt="%H:%M:%S")
    file_fmtr = logging.Formatter(_FILE_FMT, datefmt="%Y-%m-%d %H:%M:%S")

    # ---- root handler (catches EVERYTHING) ----------------------------------
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # Console (colour-coded)
    console_h = logging.StreamHandler(sys.stdout)
    console_h.setFormatter(console_fmtr)
    root.addHandler(console_h)

    # File (rotating, plain text — queried by the admin log viewer)
    _log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, "app.log")
    file_h = RotatingFileHandler(
        _log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=True,
    )
    file_h.setFormatter(file_fmtr)
    root.addHandler(file_h)

    # ---- app tree (our code) ------------------------------------------------
    logging.getLogger("app").setLevel(logging.DEBUG)

    # ---- uvicorn ------------------------------------------------------------
    # Everything flows to root. Just keep access log quiet — our middleware
    # already logs every request.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # ---- silence third-party noise ------------------------------------------
    for name in (
        "elastic_transport.transport",
        "elasticsearch",
        "urllib3",
        "httpx",
        "httpcore",
        "pymilvus",
        "neo4j",
        "sqlalchemy.engine",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


configure()
