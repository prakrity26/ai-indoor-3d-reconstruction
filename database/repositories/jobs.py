"""Job metadata queries. The API and the worker share this table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.job import JobRow
from database.session import connect


class JobRepository:
    def __init__(self, url: str) -> None:
        self.engine = connect(url)

    def insert(self, record: dict[str, Any]) -> dict[str, Any]:
        row = JobRow(
            job_id=record["job_id"],
            status=record["status"],
            filename=record["filename"],
            source_path=record["source_path"],
            ply_path=record.get("ply_path") or "",
            error=record.get("error") or "",
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
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

    def list_jobs(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.scalars(select(JobRow).order_by(JobRow.job_id)).all()
            return [_public(row) for row in rows]

    def claim_next(self) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(JobRow).where(JobRow.status == "queued").order_by(JobRow.job_id).limit(1)
            )
            if row is None:
                return None
            row.status = "running"
            row.error = ""
            session.commit()
            session.refresh(row)
            return _public(row)

    def save_status(self, job_id: str, status: str, *, ply_path: str | None = None, error: str = "") -> dict[str, Any]:
        with Session(self.engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise KeyError(job_id)
            row.status = status
            row.error = error
            if ply_path is not None:
                row.ply_path = ply_path
            session.commit()
            session.refresh(row)
            return _public(row)


def _public(row: JobRow) -> dict[str, Any]:
    return {
        "job_id": row.job_id,
        "status": row.status,
        "filename": row.filename,
        "source_path": row.source_path,
        "ply_path": row.ply_path,
        "error": row.error,
    }
