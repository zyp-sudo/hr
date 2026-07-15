from pydantic import BaseModel, Field


class JobSearchQuery(BaseModel):
    keyword: str | None = None
    city: str | None = None
    industry: str | None = None
    education: str | None = None
    experience: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    skills: list[str] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20


class JobSearchItem(BaseModel):
    id: str
    title: str
    company_name: str | None = None
    city: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    education: str | None = None
    experience: str | None = None
    industry: str | None = None
    skills: list[str] = Field(default_factory=list)
    published_at: str | None = None
    source: str | None = None


class JobSearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[JobSearchItem]
    aggregations: dict


class SkillAnalysisItem(BaseModel):
    skill: str
    count: int
    related_job_count: int


class SkillAnalysisResponse(BaseModel):
    hot_skills: list[SkillAnalysisItem]


class JobTrendResponse(BaseModel):
    by_date: list[dict]
    by_city: list[dict]
    by_industry: list[dict]
