import re
from typing import List, Sequence, Tuple


DEFAULT_ALIASES = {
    "spring boot": ["springboot", "spring mvc", "后端框架"],
    "microservices": ["微服务", "分布式服务", "service mesh"],
    "mysql": ["关系型数据库", "sql 数据库", "数据库"],
    "redis": ["缓存", "缓存中间件", "nosql"],
    "llm": ["大模型", "large language model", "aigc", "生成式ai"],
    "rag": ["检索增强", "知识库问答", "检索增强生成"],
    "vector search": ["向量检索", "embedding", "向量数据库", "faiss"],
    "kubernetes": ["k8s", "云原生", "容器编排"],
    "docker": ["容器", "容器化", "devops"],
    "etl": ["数据清洗", "数据集成", "数据管道", "数仓etl"],
    "observability": ["可观测性", "监控告警", "日志监控", "指标监控"],
    "evaluation": ["评测", "模型评测", "benchmark"],
}


def normalize_for_match(text: object) -> str:
    if text is None:
        return ""
    value = str(text).lower()
    value = re.sub(r"[\s\-_/\\.()]+", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_candidates(skill_name: object, aliases: Sequence[object] | None = None) -> List[Tuple[str, str]]:
    seen = set()
    candidates: List[Tuple[str, str]] = []
    raw_values = [skill_name] + list(aliases or [])
    for raw in raw_values:
        value = str(raw or "").strip()
        if not value:
            continue
        normalized = normalize_for_match(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append((value, normalized))

    if isinstance(skill_name, str):
        key = normalize_for_match(skill_name)
        if key in DEFAULT_ALIASES:
            for alias in DEFAULT_ALIASES[key]:
                normalized = normalize_for_match(alias)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    candidates.append((alias, normalized))
    return candidates


def skill_hits(text: object, skill_name: object, aliases: Sequence[object] | None = None) -> List[str]:
    normalized_text = normalize_for_match(text)
    if not normalized_text:
        return []

    canonical = str(skill_name or "").strip()
    if not canonical:
        return []

    for raw, normalized in build_candidates(skill_name, aliases):
        raw_lower = raw.lower().strip()
        if raw_lower in {"c++", "cpp"}:
            matched = bool(re.search(r"(?<![a-z0-9])(c\+\+|cpp)(?![a-z0-9])", str(text).lower()))
        elif re.fullmatch(r"[a-z0-9 ]+", normalized):
            matched = bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", normalized_text))
        else:
            matched = normalized in normalized_text
        if normalized and matched:
            return [canonical]
    return []
