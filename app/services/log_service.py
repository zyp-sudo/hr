"""Log-file reader, filter, and streaming service for the admin panel.

Reads the rotating log files written by :mod:`app.core.logging_config`.
The file format is::

    YYYY-MM-DD HH:MM:SS  LEVEL     logger_name  message text here...
"""

from __future__ import annotations

import asyncio
import os
import re
from collections import Counter
from typing import AsyncGenerator

# ---------------------------------------------------------------------------
# Log-file location (mirrors logging_config.py)
# ---------------------------------------------------------------------------

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")

# Regex to parse a single file log line:
#   2026-07-17 14:32:01  INFO     app.main  Starting XH-202621 v1.0.0
# The level field is %-7s formatted (left-aligned, 7 chars wide),
# so the gap between level text and module varies by level length.
_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s{2}(?P<level>[A-Z]+)\s+"
    r"(?P<module>\S+)"
    r"\s{2}(?P<message>.*)$"
)

_LOG_FILES = [_LOG_FILE] + [f"{_LOG_FILE}.{i}" for i in range(1, 6)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_log_paths() -> list[str]:
    """Return every existing log-file path (current + rotated), newest last."""
    paths: list[str] = []
    for p in _LOG_FILES:
        if os.path.isfile(p):
            paths.append(p)
    # Sort by modification time so chronological order is preserved when we
    # read them back-to-front for the "recent first" queries.
    paths.sort(key=os.path.getmtime)
    return paths


def _parse_line(line: str) -> dict | None:
    """Parse one log line into a structured dict, or return *None*."""
    m = _LOG_LINE_RE.match(line.rstrip("\n\r"))
    if not m:
        return None
    return {
        "timestamp": m.group("timestamp"),
        "level": m.group("level"),
        "module": m.group("module"),
        "message": m.group("message"),
    }


def _match_level(entry: dict, levels: list[str] | None) -> bool:
    if not levels:
        return True
    return entry["level"] in set(levels)


def _match_module(entry: dict, module: str | None) -> bool:
    if not module:
        return True
    return module.lower() in entry["module"].lower()


def _match_search(entry: dict, search: str | None) -> bool:
    if not search:
        return True
    q = search.lower()
    return q in entry["message"].lower() or q in entry["module"].lower()


def _match_time(entry: dict, start: str | None, end: str | None) -> bool:
    ts = entry["timestamp"]
    if start and ts < start:
        return False
    if end and ts > end:
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_logs(
    level: str | None = None,
    module: str | None = None,
    search: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Return a page of parsed log entries, newest first.

    Parameters
    ----------
    level:
        Comma-separated level names, e.g. ``"ERROR,WARNING"``.
    module:
        Substring match against the logger name.
    search:
        Substring match against message *and* module name.
    start_time / end_time:
        ISO-ish timestamps like ``"2026-07-17 00:00:00"``.
    page / page_size:
        1-indexed pagination.
    """
    levels = [lv.strip().upper() for lv in level.split(",") if lv.strip()] if level else None

    all_entries: list[dict] = []
    for path in reversed(_collect_log_paths()):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    entry = _parse_line(line)
                    if entry is None:
                        continue
                    if not _match_level(entry, levels):
                        continue
                    if not _match_module(entry, module):
                        continue
                    if not _match_search(entry, search):
                        continue
                    if not _match_time(entry, start_time, end_time):
                        continue
                    all_entries.append(entry)
        except FileNotFoundError:
            continue

    # Reverse so newest entries come first
    all_entries.reverse()

    total = len(all_entries)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_entries = all_entries[start_idx:end_idx]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size) if total else 0,
        "items": page_entries,
    }


def log_stats(
    level: str | None = None,
    module: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    """Aggregate log counts by level and module."""
    levels = [lv.strip().upper() for lv in level.split(",") if lv.strip()] if level else None

    level_counter: Counter[str] = Counter()
    module_counter: Counter[str] = Counter()
    total = 0

    for path in reversed(_collect_log_paths()):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    entry = _parse_line(line)
                    if entry is None:
                        continue
                    if not _match_level(entry, levels):
                        continue
                    if not _match_module(entry, module):
                        continue
                    if not _match_time(entry, start_time, end_time):
                        continue
                    total += 1
                    level_counter[entry["level"]] += 1
                    module_counter[entry["module"]] += 1
        except FileNotFoundError:
            continue

    return {
        "total": total,
        "by_level": dict(level_counter.most_common()),
        "by_module": [
            {"module": mod, "count": cnt}
            for mod, cnt in module_counter.most_common(30)
        ],
    }


async def stream_logs(
    level: str | None = None,
    module: str | None = None,
    search: str | None = None,
) -> AsyncGenerator[str, None]:
    """SSE async generator — tail the log file, pushing new lines as they appear.

    First sends the last 20 matching lines as a backlog, then watches for
    new lines appended to the current log file.
    """
    levels = [lv.strip().upper() for lv in level.split(",") if lv.strip()] if level else None

    # -- backlog: push last 20 matching lines ---------------------------------
    backlog: list[dict] = []
    if os.path.isfile(_LOG_FILE):
        with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                entry = _parse_line(line)
                if entry is None:
                    continue
                if not _match_level(entry, levels):
                    continue
                if not _match_module(entry, module):
                    continue
                if not _match_search(entry, search):
                    continue
                backlog.append(entry)

    # Send the most recent lines first
    for entry in backlog[-20:]:
        import json
        yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

    # -- tail: watch for new lines --------------------------------------------
    if not os.path.isfile(_LOG_FILE):
        return

    with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(0, os.SEEK_END)  # start at the end
        while True:
            line = fh.readline()
            if line:
                entry = _parse_line(line)
                if entry is not None:
                    if not _match_level(entry, levels):
                        continue
                    if not _match_module(entry, module):
                        continue
                    if not _match_search(entry, search):
                        continue
                    import json
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            else:
                # No new data — wait and retry
                await asyncio.sleep(0.5)
