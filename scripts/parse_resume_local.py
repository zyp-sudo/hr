import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree

import job_taxonomy as taxonomy


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESUME_SAMPLES_PATH = DATA_DIR / "resume_samples.csv"
OUTPUT_DIR = DATA_DIR / "resumes"
OUTPUT_PATH = OUTPUT_DIR / "parsed_resumes.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "resume_parse_manifest.json"


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def rel(path):
    return path.relative_to(ROOT).as_posix()


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_resume_samples():
    if not RESUME_SAMPLES_PATH.exists():
        return []
    with RESUME_SAMPLES_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {
                "resume_id": row.get("id") or row.get("name") or "sample",
                "source_path": rel(RESUME_SAMPLES_PATH),
                "text": row.get("text", ""),
                "parser": "csv_sample_text",
            }
            for row in csv.DictReader(file)
        ]


def read_docx(path):
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    texts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
    return "\n".join(texts)


def read_pdf(path):
    try:
        import pypdf

        reader = pypdf.PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if normalize_text(text):
            return text, "pypdf_text"
    except Exception:
        pass

    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "resume.txt"
            subprocess.run([pdftotext, str(path), str(output)], check=False, capture_output=True, text=True)
            if output.exists():
                text = output.read_text(encoding="utf-8", errors="ignore")
                if normalize_text(text):
                    return text, "pdftotext_cli"
    return "", "pdf_text_unavailable_local_ocr_needed"


def read_image_ocr(path):
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = ocr.ocr(str(path), cls=True)
        lines = []
        for page in result:
            for item in page:
                lines.append(item[1][0])
        return "\n".join(lines), "paddleocr_local"
    except Exception:
        pass

    tesseract = shutil.which("tesseract")
    if tesseract:
        proc = subprocess.run([tesseract, str(path), "stdout", "-l", "chi_sim+eng"], check=False, capture_output=True, text=True)
        if normalize_text(proc.stdout):
            return proc.stdout, "tesseract_local"
    return "", "image_ocr_unavailable"


def read_file_resume(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore"), "plain_text"
    if suffix == ".docx":
        return read_docx(path), "docx_local_xml"
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        return read_image_ocr(path)
    return path.read_text(encoding="utf-8", errors="ignore"), "plain_text_fallback"


def extract_projects(text):
    projects = []
    for sentence in re.split(r"[。；;\n]", text):
        sentence = normalize_text(sentence)
        if len(sentence) > 12 and any(key in sentence.lower() for key in ["项目", "project", "负责", "开发", "实现"]):
            projects.append(sentence[:180])
        if len(projects) >= 5:
            break
    return projects


def parse_item(item):
    text = item["text"]
    parsed = taxonomy.parse_resume_text(text)
    return {
        "resume_id": item["resume_id"],
        "source_path": item["source_path"],
        "parser": item["parser"],
        "parsed_at": now_iso(),
        "text_length": len(text),
        "skills": parsed["skills"],
        "capability_dimensions": parsed["dimensions"],
        "years": parsed["years"],
        "education": parsed["education"],
        "projects": extract_projects(text),
        "raw_text_preview": normalize_text(text)[:500],
    }


def _can_import(module_name):
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def build(paths):
    items = []
    if paths:
        for raw in paths:
            path = Path(raw).resolve()
            text, parser = read_file_resume(path)
            items.append({
                "resume_id": path.stem,
                "source_path": str(path),
                "text": text,
                "parser": parser,
            })
    else:
        items = read_resume_samples()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parsed = [parse_item(item) for item in items]
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for row in parsed:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": now_iso(),
        "mode": "local_only",
        "input_count": len(items),
        "parsed_count": len(parsed),
        "output": rel(OUTPUT_PATH),
        "ocr_engines": {
            "paddleocr_importable": _can_import("paddleocr"),
            "tesseract_cli": bool(shutil.which("tesseract")),
            "pdftotext_cli": bool(shutil.which("pdftotext")),
        },
        "notes": [
            "No resume content is sent to any remote API.",
            "Text PDF and DOCX are parsed locally.",
            "Images use local PaddleOCR first, then local Tesseract if installed.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build(sys.argv[1:])
