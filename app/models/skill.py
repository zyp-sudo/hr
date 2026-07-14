from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        Index("idx_skills_category_level", "category", "level"),
        Index("idx_skills_heat", "heat"),
        {"comment": "技能表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="技能ID")
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True, comment="技能名称")
    category: Mapped[str | None] = mapped_column(String(100), index=True, comment="技能类别")
    level: Mapped[str | None] = mapped_column(String(50), index=True, comment="技能等级")
    heat: Mapped[float] = mapped_column(Float, default=0, nullable=False, index=True, comment="技能热度")
    related_job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="相关岗位数量")

    job_links = relationship("JobSkill", back_populates="skill", cascade="all, delete-orphan")
    user_links = relationship("UserSkill", back_populates="skill", cascade="all, delete-orphan")


class UserSkill(TimestampMixin, Base):
    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uk_user_skill"),
        Index("idx_user_skills_user_level", "user_id", "level"),
        {"comment": "用户技能表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="用户技能ID")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    skill_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("skills.id"), nullable=False, index=True, comment="技能ID")
    level: Mapped[str | None] = mapped_column(String(50), index=True, comment="用户技能等级")
    proficiency: Mapped[float] = mapped_column(Float, default=0, nullable=False, comment="熟练度 0-100")

    user = relationship("User", back_populates="skill_links")
    skill = relationship("Skill", back_populates="user_links")
