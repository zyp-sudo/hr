import json
import math
import re
from collections import Counter

from bilingual_matching import normalize_for_match, skill_hits


SKILL_ALIASES = {
    "Java": ["java", "jvm", "spring", "spring boot", "spring cloud"],
    "Python": ["python", "django", "flask", "fastapi"],
    "Go": ["go", "golang"],
    "C++": ["c++", "cpp"],
    "JavaScript": ["javascript", "typescript", "node.js", "nodejs"],
    "React": ["react", "next.js", "nextjs"],
    "Vue": ["vue", "vue.js"],
    "SQL": ["sql", "mysql", "postgresql", "oracle", "数据库"],
    "Redis": ["redis", "缓存"],
    "Kafka": ["kafka", "消息队列"],
    "Docker": ["docker", "容器"],
    "Kubernetes": ["kubernetes", "k8s", "云原生", "容器编排"],
    "Linux": ["linux"],
    "Microservices": ["microservice", "microservices", "微服务", "分布式"],
    "DevOps": ["devops", "ci/cd", "自动化部署", "工程效能"],
    "Big Data": ["大数据", "hadoop", "spark", "flink", "hive"],
    "Data Warehouse": ["数据仓库", "数仓", "etl"],
    "Machine Learning": ["机器学习", "machine learning", "tensorflow", "pytorch", "sklearn"],
    "Deep Learning": ["深度学习", "神经网络"],
    "NLP": ["nlp", "自然语言处理", "语义分析", "命名实体"],
    "LLM": ["llm", "大模型", "large language model", "aigc", "生成式ai"],
    "RAG": ["rag", "检索增强", "知识库问答"],
    "Vector Search": ["向量检索", "embedding", "向量数据库", "faiss"],
    "Testing": ["测试", "qa", "自动化测试", "性能测试"],
    "Security": ["安全", "风控", "攻防", "漏洞", "合规"],
    "Product": ["产品经理", "产品"],
    "Marketing": ["marketing", "增长", "运营", "seo", "商业化"],
    "Design": ["设计", "ui", "ux", "交互", "视觉"],
    "Excel": ["excel", "vlookup", "pivot"],
    "Unity": ["unity", "cocos", "游戏引擎"],
    "Android": ["android", "kotlin"],
    "iOS": ["ios", "swift", "objective-c"],
    "Prompt Engineering": ["prompt", "提示词", "prompt engineering"],
}


SKILL_DIMENSIONS = {
    "Java": "编程语言",
    "Python": "编程语言",
    "Go": "编程语言",
    "C++": "编程语言",
    "JavaScript": "编程语言",
    "React": "前端开发",
    "Vue": "前端开发",
    "Android": "移动客户端",
    "iOS": "移动客户端",
    "Unity": "游戏客户端",
    "SQL": "数据技术",
    "Redis": "数据存储",
    "Kafka": "中间件",
    "Docker": "云原生",
    "Kubernetes": "云原生",
    "Linux": "基础设施",
    "Microservices": "系统架构",
    "DevOps": "工程效能",
    "Big Data": "数据工程",
    "Data Warehouse": "数据工程",
    "Machine Learning": "人工智能",
    "Deep Learning": "人工智能",
    "NLP": "人工智能",
    "LLM": "人工智能",
    "RAG": "人工智能",
    "Vector Search": "人工智能",
    "Prompt Engineering": "人工智能",
    "Testing": "质量保障",
    "Security": "安全合规",
    "Product": "产品运营",
    "Marketing": "产品运营",
    "Design": "设计体验",
    "Excel": "办公分析",
}


CAPABILITY_GROUPS = {
    "编程语言": "工程基础能力",
    "前端开发": "工程研发能力",
    "移动客户端": "工程研发能力",
    "游戏客户端": "工程研发能力",
    "数据技术": "数据能力",
    "数据存储": "数据能力",
    "中间件": "工程基础能力",
    "云原生": "基础设施能力",
    "基础设施": "基础设施能力",
    "系统架构": "工程研发能力",
    "工程效能": "工程研发能力",
    "数据工程": "数据能力",
    "人工智能": "智能技术能力",
    "质量保障": "工程质量能力",
    "安全合规": "安全能力",
    "产品运营": "业务能力",
    "设计体验": "体验能力",
    "办公分析": "通用能力",
}


CATEGORY_RULES = [
    ("ai_algorithm", ["大模型", "aigc", "人工智能", "机器学习", "深度学习", "算法", "nlp", "llm", "rag", "模型"]),
    ("data_engineering", ["大数据", "数据开发", "数据工程", "数据仓库", "数仓", "数据分析", "bi", "etl", "hadoop", "spark", "flink", "hive"]),
    ("frontend_client", ["前端", "frontend", "front end", "react", "vue", "android", "ios", "客户端", "移动端", "小游戏", "unity"]),
    ("cloud_infra", ["云原生", "云计算", "运维", "sre", "devops", "kubernetes", "k8s", "docker", "linux", "基础架构", "platform engineer"]),
    ("security", ["安全", "security", "风控", "攻防", "漏洞", "合规"]),
    ("testing_quality", ["测试", "testing", "qa", "quality assurance", "质量", "自动化测试", "性能测试"]),
    ("product_operation", ["产品", "运营", "商业化", "product manager", "project manager", "项目经理", "用户增长", "marketing", "sales"]),
    ("design", ["设计", "design", "交互", "ui", "ux", "视觉", "用研"]),
    ("backend_engineering", ["后台", "后端", "backend", "server", "java", "golang", "go", "c++", "分布式", "微服务", "接口"]),
]


ROLE_RULES = [
    ("java-backend-engineer", "Java 后端工程师", ["java", "spring", "后端", "后台"]),
    ("backend-engineer", "后端工程师", ["backend", "server", "后端", "后台", "服务端", "微服务"]),
    ("frontend-engineer", "前端工程师", ["frontend", "front end", "前端", "react", "vue", "web"]),
    ("mobile-engineer", "移动端工程师", ["android", "ios", "客户端", "移动端", "sdk"]),
    ("game-client-engineer", "游戏客户端工程师", ["unity", "cocos", "游戏客户端", "小游戏", "渲染"]),
    ("ai-algorithm-engineer", "AI 算法工程师", ["算法", "机器学习", "深度学习", "nlp", "llm", "大模型", "aigc"]),
    ("data-engineer", "数据工程师", ["数据开发", "数据工程", "大数据", "数仓", "etl", "hadoop", "spark", "flink"]),
    ("cloud-sre-engineer", "云原生/SRE 工程师", ["sre", "devops", "运维", "kubernetes", "k8s", "云原生"]),
    ("security-engineer", "安全工程师", ["安全", "security", "风控", "攻防", "漏洞"]),
    ("testing-engineer", "测试工程师", ["测试", "qa", "质量", "自动化测试"]),
    ("product-manager", "产品经理", ["产品经理", "产品"]),
    ("operations-specialist", "运营", ["运营", "增长", "商业化", "marketing"]),
    ("designer", "设计师", ["设计", "ui", "ux", "交互", "视觉"]),
]


EDUCATION_ORDER = {
    "": 0,
    "高中": 1,
    "大专": 2,
    "本科": 3,
    "硕士": 4,
    "博士": 5,
}


COMPILED_SKILL_CANDIDATES = {
    skill: [
        (candidate, normalize_for_match(candidate))
        for candidate in [skill] + aliases
        if normalize_for_match(candidate)
    ]
    for skill, aliases in SKILL_ALIASES.items()
}


def normalize_text(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def slug(value):
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value).strip("-")
    return value or "unknown"


def extract_skill_evidence(text):
    normalized = normalize_text(text)
    normalized_for_match = normalize_for_match(normalized)
    found = []
    for skill, candidates in COMPILED_SKILL_CANDIDATES.items():
        for candidate, candidate_key in candidates:
            if candidate_key in normalized_for_match:
                found.append({
                    "skill": skill,
                    "matched": candidate,
                    "dimension": SKILL_DIMENSIONS.get(skill, "其他能力"),
                })
                break
    return found


def extract_skills(text):
    return [item["skill"] for item in extract_skill_evidence(text)]


def classify_job(title, category, responsibility, requirement, skills):
    text = " ".join([title, category, responsibility, requirement, " ".join(skills)]).lower()
    for category_id, keywords in CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return category_id
    return "other"


def infer_role(title, category, normalized_category, skills):
    text = " ".join([title, category, normalized_category, " ".join(skills)]).lower()
    for role_id, role_name, keywords in ROLE_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return role_id, role_name
    cleaned = re.sub(r"[（(].*?[）)]", "", normalize_text(title))
    cleaned = re.sub(r"(高级|资深|专家|实习|校招|社招|初级|中级|senior|staff|principal)", "", cleaned, flags=re.I)
    cleaned = normalize_text(cleaned) or normalized_category or "其他岗位"
    return f"role-{slug(cleaned)}", cleaned


def capability_dimensions(skills):
    result = []
    for skill in skills:
        dimension = SKILL_DIMENSIONS.get(skill, "其他能力")
        group = CAPABILITY_GROUPS.get(dimension, "其他能力")
        if group not in result:
            result.append(group)
    return result


def capability_scores(skills):
    counts = Counter(capability_dimensions(skills))
    total = max(1, sum(counts.values()))
    return {
        dimension: round(count / total * 100, 2)
        for dimension, count in sorted(counts.items())
    }


def skill_evidence_json(text):
    return json.dumps(extract_skill_evidence(text), ensure_ascii=False, separators=(",", ":"))


def capability_scores_json(skills):
    return json.dumps(capability_scores(skills), ensure_ascii=False, separators=(",", ":"))


def extract_required_years(text):
    text = normalize_text(text)
    values = []
    for match in re.finditer(r"(\d{1,2})\s*(?:年|years?)", text, flags=re.I):
        value = int(match.group(1))
        if 0 <= value < 40:
            values.append(value)
    for chinese, value in {"一年": 1, "两年": 2, "二年": 2, "三年": 3, "四年": 4, "五年": 5, "八年": 8, "十年": 10}.items():
        if chinese in text:
            values.append(value)
    if "不限" in text:
        values.append(0)
    return min(values) if values else 0


def extract_education_level(text):
    text = normalize_text(text).lower()
    for label in ["博士", "硕士", "本科", "大专", "高中"]:
        if label in text:
            return label
    if any(term in text for term in ["master", "mba", "msc"]):
        return "硕士"
    if any(term in text for term in ["bachelor", "undergraduate"]):
        return "本科"
    return ""


def parse_resume_text(text):
    text = normalize_text(text)
    years = extract_required_years(text)
    education = extract_education_level(text)
    skills = extract_skills(text)
    dimensions = capability_dimensions(skills)
    return {
        "skills": skills,
        "years": years,
        "education": education,
        "dimensions": dimensions,
    }


def score_application(job, applicant, outcome_label=""):
    required_skills = [item for item in str(job.get("normalized_skills", "")).split("|") if item]
    applicant_skills = set(applicant.get("skills") or [])
    matched = [skill for skill in required_skills if skill in applicant_skills]
    missing = [skill for skill in required_skills if skill not in applicant_skills]

    skill_match = len(matched) / len(required_skills) if required_skills else 0.45
    job_dimensions = set(capability_dimensions(required_skills))
    applicant_dimensions = set(applicant.get("dimensions") or [])
    dimension_match = len(job_dimensions & applicant_dimensions) / len(job_dimensions) if job_dimensions else 0.45

    required_years = extract_required_years(" ".join([
        job.get("work_years", ""),
        job.get("requirement", ""),
    ]))
    applicant_years = int(applicant.get("years") or 0)
    if required_years <= 0:
        experience_score = 0.75 if applicant_years else 0.55
    else:
        experience_score = min(1.0, applicant_years / required_years)

    required_education = extract_education_level(job.get("requirement", ""))
    applicant_education = applicant.get("education", "")
    required_rank = EDUCATION_ORDER.get(required_education, 0)
    applicant_rank = EDUCATION_ORDER.get(applicant_education, 0)
    education_score = 1.0 if required_rank == 0 or applicant_rank >= required_rank else max(0.35, applicant_rank / required_rank)

    quality_factor = float(job.get("quality_score") or 0) / 100
    relative_score = (
        skill_match * 0.45
        + dimension_match * 0.2
        + experience_score * 0.2
        + education_score * 0.1
        + quality_factor * 0.05
    )

    if str(outcome_label).strip() in {"1", "true", "success", "hired", "offer", "录用", "成功"}:
        relative_score = min(1.0, relative_score + 0.08)
    elif str(outcome_label).strip() in {"0", "false", "reject", "rejected", "失败"}:
        relative_score = max(0.0, relative_score - 0.08)

    # A calibrated heuristic until real application outcome history is available.
    probability = 1 / (1 + math.exp(-5.2 * (relative_score - 0.58)))
    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_match_rate": round(skill_match, 4),
        "dimension_match_rate": round(dimension_match, 4),
        "experience_match_score": round(experience_score, 4),
        "education_match_score": round(education_score, 4),
        "relative_ability_score": round(relative_score * 100, 2),
        "success_probability": round(probability, 4),
        "scoring_basis": "rule_based_skill_dimension_experience_education_quality",
    }
