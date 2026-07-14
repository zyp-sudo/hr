from sqlalchemy import BigInteger, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class MatchResult(TimestampMixin, Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uk_user_job_match"),
        Index("idx_match_results_user_score", "user_id", "match_score"),
        Index("idx_match_results_job_score", "job_id", "match_score"),
        {"comment": "人岗匹配结果表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="匹配结果ID")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False, index=True, comment="岗位ID")
    resume_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("resumes.id"), index=True, comment="简历ID")
    match_score: Mapped[float] = mapped_column(Float, nullable=False, index=True, comment="匹配度 0-100")
    matched_skills: Mapped[list | None] = mapped_column(JSON, comment="已满足技能")
    missing_skills: Mapped[list | None] = mapped_column(JSON, comment="缺失技能")
    learning_path: Mapped[list | None] = mapped_column(JSON, comment="推荐学习路径")
    detail: Mapped[dict | None] = mapped_column(JSON, comment="匹配解释、证据链和模型输出")

    user = relationship("User", back_populates="match_results")
    job = relationship("Job", back_populates="match_results")
    resume = relationship("Resume")
