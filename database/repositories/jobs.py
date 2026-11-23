"""Job (project) queries. The API and the worker share this table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models.job import JobRow
from database.session import connect

_EDITABLE = ("name", "description", "visibility", "share_token")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobRepository:
    def __init__(self, url: str) -> None:
        self.engine = connect(url)

    def insert(self, record: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        row = JobRow(
            job_id=record["job_id"],
            status=record["status"],
            filename=record["filename"],
            source_path=record["source_path"],
            ply_path=record.get("ply_path") or "",
            error=record.get("error") or "",
            created_at=record.get("created_at") or now,
            name=record.get("name") or "",
            description=record.get("description") or "",
            visibility=record.get("visibility") or "private",
            share_token=record.get("share_token") or "",
            stage=record.get("stage") or "",
            progress=int(record.get("progress") or 0),
            mesh_path=record.get("mesh_path") or "",
            origin=record.get("origin") or "upload",
            updated_at=now,
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _public(row)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.get(JobRow, job_id)
            return None if row is None else _public(row)

    def get_by_share_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        with Session(self.engine) as session:
            row = session.scalar(select(JobRow).where(JobRow.share_token == token).limit(1))
            return None if row is None else _public(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.scalars(select(JobRow).order_by(JobRow.created_at.desc(), JobRow.job_id)).all()
            return [_public(row) for row in rows]

    def claim_next(self) -> dict[str, Any] | None:
        """Oldest queued job becomes running. Postgres skips rows another worker holds."""
        with Session(self.engine) as session:
            query = (
                select(JobRow)
                .where(JobRow.status == "queued")
                .order_by(JobRow.created_at, JobRow.job_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = session.scalar(query)
            if row is None:
                return None
            row.status = "running"
            row.error = ""
            row.stage = "starting"
            row.progress = 0
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return _public(row)

    def save_status(
        self,
        job_id: str,
        status: str,
        *,
        ply_path: str | None = None,
        mesh_path: str | None = None,
        error: str = "",
        stage: str | None = None,
        progress: int | None = None,
    ) -> dict[str, Any]:
        with Session(self.engine) as session:
            row = _require(session, job_id)
            row.status = status
            row.error = error
            if ply_path is not None:
                row.ply_path = ply_path
            if mesh_path is not None:
                row.mesh_path = mesh_path
            if stage is not None:
                row.stage = stage
            if progress is not None:
                row.progress = max(0, min(100, int(progress)))
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return _public(row)

    def save_progress(self, job_id: str, stage: str, progress: int) -> dict[str, Any]:
        with Session(self.engine) as session:
            row = _require(session, job_id)
            row.stage = stage
            row.progress = max(0, min(100, int(progress)))
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return _public(row)

    def update_fields(self, job_id: str, **fields: Any) -> dict[str, Any]:
        unknown = set(fields) - set(_EDITABLE)
        if unknown:
            raise ValueError(f"not editable: {sorted(unknown)}")
        with Session(self.engine) as session:
            row = _require(session, job_id)
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return _public(row)

    def fail_stale(self, before: str, message: str) -> list[str]:
        """Fail running jobs whose last progress update is older than ``before`` (ISO time)."""
        with Session(self.engine) as session:
            rows = session.scalars(
                select(JobRow).where(JobRow.status == "running", JobRow.updated_at < before)
            ).all()
            for row in rows:
                row.status = "failed"
                row.error = message
                row.updated_at = _now()
            session.commit()
            return [row.job_id for row in rows]

    def delete(self, job_id: str) -> bool:
        with Session(self.engine) as session:
            result = session.execute(delete(JobRow).where(JobRow.job_id == job_id))
            session.commit()
            return bool(result.rowcount)


def _require(session: Session, job_id: str) -> JobRow:
    row = session.get(JobRow, job_id)
    if row is None:
        raise KeyError(job_id)
    return row


def _public(row: JobRow) -> dict[str, Any]:
    return {
        "job_id": row.job_id,
        "status": row.status,
        "filename": row.filename,
        "source_path": row.source_path,
        "ply_path": row.ply_path,
        "mesh_path": row.mesh_path,
        "error": row.error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "name": row.name,
        "description": row.description,
        "visibility": row.visibility,
        "share_token": row.share_token,
        "stage": row.stage,
        "progress": row.progress,
        "origin": row.origin,
    }
