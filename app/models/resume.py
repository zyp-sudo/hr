from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (
        Index("idx_resumes_user_active", "user_id", "is_active"),
        {"comment": "简历表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="简历ID")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    title: Mapped[str | None] = mapped_column(String(255), comment="简历标题")
    raw_text: Mapped[str | None] = mapped_column(Text, comment="简历原文")
    education: Mapped[list | None] = mapped_column(JSON, comment="教育背景结构化数据")
    projects: Mapped[list | None] = mapped_column(JSON, comment="项目经历结构化数据")
    skill_tags: Mapped[list | None] = mapped_column(JSON, comment="技能标签")
    job_intention: Mapped[dict | None] = mapped_column(JSON, comment="求职意向")
    parse_status: Mapped[str] = mapped_column(String(50), default="parsed", nullable=False, index=True, comment="解析状态")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True, comment="是否当前有效简历")

    user = relationship("User", back_populates="resumes")
