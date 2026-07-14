from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("idx_companies_industry_region", "industry", "region"),
        {"comment": "企业表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="企业ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True, comment="企业名称")
    industry: Mapped[str | None] = mapped_column(String(100), index=True, comment="行业")
    size: Mapped[str | None] = mapped_column(String(50), comment="企业规模")
    region: Mapped[str | None] = mapped_column(String(100), index=True, comment="地区")
    description: Mapped[str | None] = mapped_column(Text, comment="企业简介")
    recruiting_job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="招聘岗位数量")

    jobs = relationship("Job", back_populates="company", cascade="save-update")
