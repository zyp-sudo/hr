from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_city_target", "city", "target_position"),
        {"comment": "用户表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    name: Mapped[str] = mapped_column(String(120), nullable=False, comment="用户姓名")
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(50), index=True, comment="手机号")
    city: Mapped[str | None] = mapped_column(String(100), index=True, comment="所在城市")
    education_summary: Mapped[dict | None] = mapped_column(JSON, comment="教育背景摘要")
    project_summary: Mapped[dict | None] = mapped_column(JSON, comment="项目经历摘要")
    target_position: Mapped[str | None] = mapped_column(String(255), index=True, comment="求职意向岗位")
    target_city: Mapped[str | None] = mapped_column(String(100), index=True, comment="求职意向城市")
    expected_salary_min: Mapped[int | None] = mapped_column(comment="期望最低薪资")
    expected_salary_max: Mapped[int | None] = mapped_column(comment="期望最高薪资")

    # ---- Auth fields --------------------------------------------------------
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="bcrypt 密码哈希"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="账户是否激活"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", comment="角色: admin / user"
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None,
        comment="当前活跃会话ID，用于单点登录强制——新登录会覆盖旧会话"
    )

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    skill_links = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    match_results = relationship("MatchResult", back_populates="user", cascade="all, delete-orphan")
