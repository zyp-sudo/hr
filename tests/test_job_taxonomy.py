from scripts import job_taxonomy as taxonomy


def test_extract_skills_and_evidence():
    text = "熟悉 Java Spring Boot、MySQL、Redis、Docker 和 K8s"
    skills = taxonomy.extract_skills(text)
    assert {"Java", "SQL", "Redis", "Docker", "Kubernetes"}.issubset(skills)
    assert all({"skill", "matched", "dimension"} <= set(item) for item in taxonomy.extract_skill_evidence(text))


def test_classification_role_and_capabilities():
    skills = ["Python", "Machine Learning", "Docker"]
    assert taxonomy.classify_job("大模型算法工程师", "", "", "", skills) == "ai_algorithm"
    assert taxonomy.infer_role("大模型算法工程师", "", "ai_algorithm", skills)[0] == "ai-algorithm-engineer"
    assert set(taxonomy.capability_dimensions(skills)) == {"工程基础能力", "智能技术能力", "基础设施能力"}
    assert round(sum(taxonomy.capability_scores(skills).values()), 1) == 100.0


def test_resume_fields_and_application_score():
    resume = taxonomy.parse_resume_text("5年 Java 和 MySQL 开发经验，本科学历")
    assert resume["years"] == 5
    assert resume["education"] == "本科"
    assert {"Java", "SQL"}.issubset(resume["skills"])
    job = {
        "normalized_skills": "Java|SQL",
        "work_years": "3年",
        "requirement": "本科，3年经验",
        "quality_score": 90,
    }
    result = taxonomy.score_application(job, resume)
    assert result["relative_ability_score"] >= 80
    assert result["missing_skills"] == []


def test_normalizers_and_serializers():
    assert taxonomy.slug(" Java / 后端 ") == "java-后端"
    assert taxonomy.extract_required_years("三年以上经验") == 3
    assert taxonomy.extract_education_level("Master degree") == "硕士"
    assert "Java" in taxonomy.skill_evidence_json("Spring Boot")
    assert taxonomy.capability_scores_json(["Java"]).startswith("{")
