"""Job (project) row. Video bytes and 3D files stay on disk; this table holds metadata."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    ply_path: Mapped[str] = mapped_column(String, nullable=False, default="")
    error: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    # 002_projects
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String, nullable=False, default="private")
    share_token: Mapped[str] = mapped_column(String, nullable=False, default="")
    stage: Mapped[str] = mapped_column(String, nullable=False, default="")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mesh_path: Mapped[str] = mapped_column(String, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String, nullable=False, default="upload")
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default="")
    # 003_splat
    splat_status: Mapped[str] = mapped_column(String, nullable=False, default="none")
    splat_stage: Mapped[str] = mapped_column(String, nullable=False, default="")
    splat_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    splat_error: Mapped[str] = mapped_column(String, nullable=False, default="")
    splat_worker: Mapped[str] = mapped_column(String, nullable=False, default="")
    splat_updated_at: Mapped[str] = mapped_column(String, nullable=False, default="")
