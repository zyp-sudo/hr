import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "pipeline_manifest.json"


STEPS = [
    ("etl", ["scripts/etl_unify_jobs.py"]),
    ("knowledge_graph", ["scripts/build_knowledge_graph.py"]),
    ("architecture_exports", ["scripts/export_architecture_artifacts.py"]),
    ("deepseek_extraction", ["scripts/deepseek_extract.py"]),
    ("local_resume_parse", ["scripts/parse_resume_local.py"]),
]


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def run_step(name, args):
    command = [sys.executable] + args
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {
        "name": name,
        "command": " ".join(command),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main():
    results = []
    failed = False
    for name, args in STEPS:
        result = run_step(name, args)
        results.append(result)
        if result["returncode"] != 0:
            failed = True
            break

    manifest = {
        "generated_at": now_iso(),
        "status": "failed" if failed else "ok",
        "steps": results,
        "outputs": [
            "data/etl/unified_jobs.csv",
            "data/kg/nodes.csv",
            "data/warehouse/architecture_manifest.json",
            "data/ai/deepseek_extractions.jsonl",
            "data/resumes/parsed_resumes.jsonl",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
