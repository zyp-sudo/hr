SEARCH_TEXT = {
    "type": "text",
    "analyzer": "standard",
    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
}


COMMON_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "5s",
}


JOB_INDEX = "job_index"
SKILL_INDEX = "skill_index"
COMPANY_INDEX = "company_index"
RESUME_INDEX = "resume_index"


INDEX_MAPPINGS = {
    JOB_INDEX: {
        "settings": {**COMMON_SETTINGS, "max_result_window": 100_000},
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": SEARCH_TEXT,
                "company_id": {"type": "keyword"},
                "company_name": SEARCH_TEXT,
                "city": {"type": "keyword"},
                "province": {"type": "keyword"},
                "country": {"type": "keyword"},
                "salary_min": {"type": "integer"},
                "salary_max": {"type": "integer"},
                "salary_text": {"type": "keyword"},
                "education": {"type": "keyword"},
                "experience": {"type": "keyword"},
                "description": SEARCH_TEXT,
                "requirement": SEARCH_TEXT,
                "industry": {"type": "keyword"},
                "job_type": {"type": "keyword"},
                "source": {"type": "keyword"},
                "source_url": {"type": "keyword", "index": False},
                "published_at": {"type": "date"},
                "collected_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "skills": {"type": "keyword"},
                "skill_text": SEARCH_TEXT,
                "required_skills": {"type": "keyword"},
                "quality_score": {"type": "integer"},
                "quality_level": {"type": "keyword"},
                "content_hash": {"type": "keyword"},
                "sync_hash": {"type": "keyword"},
            }
        },
    },
    SKILL_INDEX: {
        "settings": COMMON_SETTINGS,
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "name": SEARCH_TEXT,
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
                "name": SEARCH_TEXT,
                "industry": {"type": "keyword"},
                "size": {"type": "keyword"},
                "region": {"type": "keyword"},
                "description": SEARCH_TEXT,
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
                "title": SEARCH_TEXT,
                "raw_text": SEARCH_TEXT,
                "education_text": SEARCH_TEXT,
                "project_text": SEARCH_TEXT,
                "skill_tags": {"type": "keyword"},
                "job_intention": {"type": "keyword"},
                "parse_status": {"type": "keyword"},
                "is_active": {"type": "boolean"},
                "updated_at": {"type": "date"},
            }
        },
    },
}
