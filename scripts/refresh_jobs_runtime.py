"""Run a safe job refresh and publish the result to runtime stores."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(ROOT / "scripts" / script), *args]
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy())
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    os.environ["CRAWL_RESET"] = "0"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONUTF8"] = "1"
    run("crawl_jobs_100k.py")
    run("bootstrap_storage.py", "--sync")
    run("sync_mysql_to_es.py", "--auto")


if __name__ == "__main__":
    main()
