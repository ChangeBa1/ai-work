"""SQLAlchemy 2.x async engine and tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TestRunRow(Base):
    __tablename__ = "test_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_case_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    report_html_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class StepRecordRow(Base):
    __tablename__ = "step_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step_id: Mapped[str] = mapped_column(String(128))
    final_status: Mapped[str] = mapped_column(String(32))
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ActionIterationRow(Base):
    __tablename__ = "action_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step_id: Mapped[str] = mapped_column(String(128))
    iteration_index: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class RecoveryAttemptRow(Base):
    __tablename__ = "recovery_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step_id: Mapped[str] = mapped_column(String(128))
    iteration_index: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class VisualExperienceRow(Base):
    __tablename__ = "visual_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step_id: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PageMemoryRow(Base):
    """Feature 015 (FR-003): one remembered page (payload = PageMemory JSON)."""

    __tablename__ = "page_memories"

    page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resolution_w: Mapped[int] = mapped_column(Integer)
    resolution_h: Mapped[int] = mapped_column(Integer)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ElementMemoryRow(Base):
    """Feature 015 (FR-003): one remembered element (payload = ElementMemory JSON)."""

    __tablename__ = "element_memories"

    element_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    page_id: Mapped[str] = mapped_column(String(64), index=True)
    target_label: Mapped[str] = mapped_column(String(512), index=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


def make_engine(db_path: str) -> AsyncEngine:
    # Ensure parent dir exists for sqlite file
    from pathlib import Path

    p = Path(db_path)
    if p.parent and str(p.parent) not in (".", ""):
        p.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{p.as_posix()}"
    return create_async_engine(url, echo=False)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
