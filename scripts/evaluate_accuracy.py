"""Run the reproducible MVP accuracy benchmark.

This benchmark measures deterministic extraction and matching behavior. It is
not a substitute for an independently annotated production corpus; that scope
is stated explicitly in docs/mvp-scope.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts import job_taxonomy as taxonomy
except ModuleNotFoundError:  # Direct execution: python scripts/evaluate_accuracy.py
    import job_taxonomy as taxonomy


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "accuracy_report.json"

SKILL_SPECS = [
    ("Java Spring Boot", {"Java"}),
    ("Python FastAPI", {"Python"}),
    ("Golang", {"Go"}),
    ("C++", {"C++"}),
    ("TypeScript Node.js", {"JavaScript"}),
    ("React Next.js", {"React"}),
    ("Vue.js", {"Vue"}),
    ("MySQL PostgreSQL", {"SQL"}),
    ("Redis 缓存", {"Redis"}),
    ("Kafka 消息队列", {"Kafka"}),
    ("Docker 容器化", {"Docker"}),
    ("Kubernetes K8s", {"Kubernetes"}),
    ("Linux", {"Linux"}),
    ("微服务架构", {"Microservices"}),
    ("CI/CD DevOps", {"DevOps"}),
    ("Hadoop Spark", {"Big Data"}),
    ("数据仓库 ETL", {"Data Warehouse"}),
    ("PyTorch 机器学习", {"Machine Learning"}),
    ("深度学习 神经网络", {"Deep Learning"}),
    ("大模型 LLM", {"LLM"}),
]

SKILL_TEMPLATES = [
    "{value}",
    "核心技术：{value}",
    "岗位要求熟悉 {value}，能够独立交付。",
    "Hands-on skills: {value}.",
]

CATEGORY_SPECS = [
    ("Java 后端工程师", "backend_engineering"),
    ("大模型算法工程师", "ai_algorithm"),
    ("大数据开发工程师", "data_engineering"),
    ("React 前端工程师", "frontend_client"),
    ("云原生 SRE 工程师", "cloud_infra"),
    ("网络安全工程师", "security"),
    ("自动化测试工程师", "testing_quality"),
    ("产品经理", "product_operation"),
    ("UI 交互设计师", "design"),
]

RESUME_SPECS = [
    ("5年 Java 开发经验，本科学历", {"Java"}, 5, "本科"),
    ("3 years Python experience, master degree", {"Python"}, 3, "硕士"),
    ("两年 Docker Kubernetes 项目经验，大专", {"Docker", "Kubernetes"}, 2, "大专"),
    ("8年 MySQL Redis 后端经验，硕士", {"SQL", "Redis"}, 8, "硕士"),
    ("1年 React Vue 前端经验，本科", {"React", "Vue"}, 1, "本科"),
]


def _set_metrics(pairs: list[tuple[set[str], set[str]]]) -> dict[str, float]:
    tp = sum(len(predicted & expected) for predicted, expected in pairs)
    fp = sum(len(predicted - expected) for predicted, expected in pairs)
    fn = sum(len(expected - predicted) for predicted, expected in pairs)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def run_benchmark() -> dict:
    skill_pairs: list[tuple[set[str], set[str]]] = []
    for phrase, expected in SKILL_SPECS:
        for template in SKILL_TEMPLATES:
            predicted = set(taxonomy.extract_skills(template.format(value=phrase)))
            skill_pairs.append((predicted, expected))

    category_total = 0
    category_correct = 0
    for title, expected in CATEGORY_SPECS:
        for suffix in ("", "（正式岗位）", "，负责核心系统", "，欢迎投递", "，工作地点深圳"):
            value = title + suffix
            predicted = taxonomy.classify_job(value, "", "", "", taxonomy.extract_skills(value))
            category_total += 1
            category_correct += int(predicted == expected)

    resume_total = 0
    resume_correct = 0
    for text, skills, years, education in RESUME_SPECS:
        for prefix in ("", "个人简介：", "候选人经历：", "简历摘要："):
            parsed = taxonomy.parse_resume_text(prefix + text)
            resume_total += 1
            resume_correct += int(
                set(parsed["skills"]) == skills
                and parsed["years"] == years
                and parsed["education"] == education
            )

    match_total = 0
    match_correct = 0
    for _, skills in SKILL_SPECS[:10]:
        required = sorted(skills)
        job = {
            "normalized_skills": "|".join(required),
            "work_years": "3年",
            "requirement": "本科及以上，3年相关经验",
            "quality_score": 95,
        }
        for expected, applicant in (
            (True, {"skills": required, "dimensions": taxonomy.capability_dimensions(required), "years": 5, "education": "本科"}),
            (False, {"skills": [], "dimensions": [], "years": 0, "education": "大专"}),
        ):
            predicted = taxonomy.score_application(job, applicant)["relative_ability_score"] >= 60
            match_total += 1
            match_correct += int(predicted == expected)

    skill_metrics = _set_metrics(skill_pairs)
    metrics = {
        "jd_skill_extraction_f1": skill_metrics["f1"],
        "jd_skill_extraction_precision": skill_metrics["precision"],
        "jd_skill_extraction_recall": skill_metrics["recall"],
        "job_category_accuracy": round(category_correct / category_total, 4),
        "resume_field_accuracy": round(resume_correct / resume_total, 4),
        "match_decision_accuracy": round(match_correct / match_total, 4),
    }
    thresholds = {
        "jd_skill_extraction_f1": 0.9,
        "job_category_accuracy": 0.9,
        "resume_field_accuracy": 0.9,
        "match_decision_accuracy": 0.9,
    }
    passed = all(metrics[name] >= threshold for name, threshold in thresholds.items())
    return {
        "benchmark": "mvp_deterministic_v1",
        "case_count": len(skill_pairs) + category_total + resume_total + match_total,
        "metrics": metrics,
        "thresholds": thresholds,
        "passed": passed,
        "limitations": [
            "Cases are curated for deterministic MVP regression testing.",
            "Production accuracy requires an independently annotated, domain-stratified corpus.",
            "The match metric is binary threshold agreement, not hiring-outcome calibration.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = run_benchmark()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
