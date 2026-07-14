IK_TEXT = {
    "type": "text",
    "analyzer": "ik_max_word",
    "search_analyzer": "ik_smart",
    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
}


COMMON_SETTINGS = {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "30s",
}


JOB_INDEX = "job_index"
SKILL_INDEX = "skill_index"
COMPANY_INDEX = "company_index"
RESUME_INDEX = "resume_index"


INDEX_MAPPINGS = {
    JOB_INDEX: {
        "settings": COMMON_SETTINGS,
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "title": IK_TEXT,
                "company_id": {"type": "long"},
                "company_name": IK_TEXT,
                "city": {"type": "keyword"},
                "province": {"type": "keyword"},
                "country": {"type": "keyword"},
                "salary_min": {"type": "integer"},
                "salary_max": {"type": "integer"},
                "salary_text": {"type": "keyword"},
                "education": {"type": "keyword"},
                "experience": {"type": "keyword"},
                "description": IK_TEXT,
                "requirement": IK_TEXT,
                "industry": {"type": "keyword"},
                "job_type": {"type": "keyword"},
                "source": {"type": "keyword"},
                "source_url": {"type": "keyword", "index": False},
                "published_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "skills": {"type": "keyword"},
                "skill_text": IK_TEXT,
                "required_skills": {"type": "keyword"},
            }
        },
    },
    SKILL_INDEX: {
        "settings": COMMON_SETTINGS,
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "name": IK_TEXT,
                "name_keyword": {"type": "keyword"},
                "category": {"type": "keyword"},
                "level": {"type": "keyword"},
                "heat": {"type": "float"},
                "related_job_count": {"type": "integer"},
                "updated_at": {"type": "date"},
            }
        },
    },
    COMPANY_INDEX: {
        "settings": COMMON_SETTINGS,
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "name": IK_TEXT,
                "industry": {"type": "keyword"},
                "size": {"type": "keyword"},
                "region": {"type": "keyword"},
                "description": IK_TEXT,
                "recruiting_job_count": {"type": "integer"},
                "updated_at": {"type": "date"},
            }
        },
    },
    RESUME_INDEX: {
        "settings": COMMON_SETTINGS,
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "user_id": {"type": "long"},
                "title": IK_TEXT,
                "raw_text": IK_TEXT,
                "education_text": IK_TEXT,
                "project_text": IK_TEXT,
                "skill_tags": {"type": "keyword"},
                "job_intention": {"type": "keyword"},
                "parse_status": {"type": "keyword"},
                "is_active": {"type": "boolean"},
                "updated_at": {"type": "date"},
            }
        },
    },
}
