from scripts.bilingual_matching import skill_hits


def test_bilingual_skill_hits_with_aliases():
    text = "具备 Spring Boot、微服务、MySQL 和 Redis 的开发经验"
    assert skill_hits(text, "Spring Boot") == ["Spring Boot"]
    assert skill_hits(text, "Microservices") == ["Microservices"]
    assert skill_hits(text, "MySQL") == ["MySQL"]
    assert skill_hits(text, "Redis") == ["Redis"]


def test_chinese_english_aliases_for_llm_and_rag():
    text = "有大模型与检索增强生成（RAG）项目经验"
    assert skill_hits(text, "LLM") == ["LLM"]
    assert skill_hits(text, "RAG") == ["RAG"]
