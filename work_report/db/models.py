"""SQLAlchemy ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from work_report.timeutil import now_naive as utcnow


class Base(DeclarativeBase):
    pass


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ProjectName(Base):
    __tablename__ = "project_names"

    project_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String(32), default="cli")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    week_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    week_end: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_commits: Mapped[int] = mapped_column(Integer, default=0)
    project_count: Mapped[int] = mapped_column(Integer, default=0)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_sent: Mapped[int] = mapped_column(Integer, default=0)
    dingtalk_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    holiday_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    commits: Mapped[list[RunCommit]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunCommit.id",
    )
    logs: Mapped[list[RunLog]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunLog.id",
    )


class RunCommit(Base):
    __tablename__ = "run_commits"
    __table_args__ = (Index("ix_run_commits_run_id", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    project_name: Mapped[str] = mapped_column(String(256), default="")
    short_id: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(256), default="")
    author_email: Mapped[str] = mapped_column(String(256), default="")
    commit_created_at: Mapped[str] = mapped_column(String(64), default="")

    run: Mapped[Run] = relationship(back_populates="commits")


class RunLog(Base):
    __tablename__ = "run_logs"
    __table_args__ = (Index("ix_run_logs_run_id", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="logs")


class Holiday(Base):
    __tablename__ = "holidays"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(String(128), default="")
    is_makeup: Mapped[bool] = mapped_column(Boolean, default=False)
