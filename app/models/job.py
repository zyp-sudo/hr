from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_city_industry", "city", "industry"),
        Index("idx_jobs_salary", "salary_min", "salary_max"),
        Index("idx_jobs_publish_time", "published_at"),
        Index("idx_jobs_source_origin", "source", "source_job_id"),
        Index("idx_jobs_company_publish", "company_id", "published_at"),
        {"comment": "岗位表，10万+岗位数据核心表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="岗位ID")
    source_job_id: Mapped[str | None] = mapped_column(String(120), index=True, comment="来源站点岗位ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="岗位名称")
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("companies.id"), index=True, comment="企业ID")
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="冗余企业名称，便于检索和同步")
    city: Mapped[str | None] = mapped_column(String(100), index=True, comment="工作城市")
    province: Mapped[str | None] = mapped_column(String(100), index=True, comment="省份")
    country: Mapped[str | None] = mapped_column(String(80), default="中国", comment="国家")
    salary_min: Mapped[int | None] = mapped_column(Integer, index=True, comment="最低月薪，单位元")
    salary_max: Mapped[int | None] = mapped_column(Integer, index=True, comment="最高月薪，单位元")
    salary_text: Mapped[str | None] = mapped_column(String(100), comment="原始薪资范围文本")
    education: Mapped[str | None] = mapped_column(String(80), index=True, comment="学历要求")
    experience: Mapped[str | None] = mapped_column(String(80), index=True, comment="经验要求")
    description: Mapped[str | None] = mapped_column(Text, comment="岗位描述")
    requirement: Mapped[str | None] = mapped_column(Text, comment="任职要求")
    industry: Mapped[str | None] = mapped_column(String(100), index=True, comment="行业分类")
    job_type: Mapped[str | None] = mapped_column(String(80), index=True, comment="岗位类型")
    source: Mapped[str | None] = mapped_column(String(100), index=True, comment="数据来源")
    source_url: Mapped[str | None] = mapped_column(String(1024), comment="来源URL")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, comment="发布时间")
    raw_payload: Mapped[dict | None] = mapped_column(JSON, comment="原始数据JSON，保留追溯能力")

    company = relationship("Company", back_populates="jobs")
    skill_links = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    match_results = relationship("MatchResult", back_populates="job", cascade="all, delete-orphan")


class JobSkill(TimestampMixin, Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_id", name="uk_job_skill"),
        Index("idx_job_skills_required", "skill_id", "required"),
        {"comment": "岗位技能关联表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="岗位技能关联ID")
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False, index=True, comment="岗位ID")
    skill_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("skills.id"), nullable=False, index=True, comment="技能ID")
    required: Mapped[bool] = mapped_column(default=True, nullable=False, index=True, comment="是否必需技能")
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="匹配权重")
    level: Mapped[str | None] = mapped_column(String(50), index=True, comment="岗位要求技能等级")

    job = relationship("Job", back_populates="skill_links")
    skill = relationship("Skill", back_populates="job_links")
