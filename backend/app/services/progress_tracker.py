import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from ..database import SessionLocal
from ..models.analysis_task import AnalysisTask


TASK_TTL_HOURS = 24


def _now() -> datetime:
    return datetime.utcnow()


def _serialize(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return json.dumps({"value": str(value)})


def _deserialize(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _row_to_task(row: AnalysisTask) -> dict[str, Any]:
    return {
        "task_id": row.id,
        "user_id": int(row.user_id),
        "job_id": int(row.job_id),
        "status": row.status,
        "percent": int(row.progress or 0),
        "message": row.message or "",
        "result": _deserialize(row.result_json),
        "error": row.error_message,
        "created_at": row.created_at.timestamp() if row.created_at else None,
        "updated_at": row.updated_at.timestamp() if row.updated_at else None,
    }


def create_task(*, task_id: str, user_id: int, job_id: int) -> None:
    db = SessionLocal()
    try:
        row = AnalysisTask(
            id=task_id,
            user_id=int(user_id),
            job_id=int(job_id),
            status="running",
            progress=0,
            message="Starting...",
            expires_at=_now() + timedelta(hours=TASK_TTL_HOURS),
        )
        db.merge(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def update_task(*, task_id: str, percent: int | None = None, message: str | None = None) -> None:
    db = SessionLocal()
    try:
        row = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not row or row.status != "running":
            return
        if percent is not None:
            row.progress = max(0, min(99, int(percent)))
        if message is not None:
            row.message = str(message)
        row.updated_at = _now()
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def complete_task(*, task_id: str, result: Any) -> None:
    db = SessionLocal()
    try:
        row = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not row:
            return
        row.status = "done"
        row.progress = 100
        row.message = "Done"
        row.result_json = _serialize(result)
        row.error_message = None
        row.updated_at = _now()
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def fail_task(*, task_id: str, error_message: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not row:
            return
        row.status = "error"
        row.error_message = str(error_message or "Failed")
        row.message = row.error_message
        row.progress = max(0, min(99, int(row.progress or 0)))
        row.updated_at = _now()
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def get_task(*, task_id: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        return _row_to_task(row) if row else None
    finally:
        db.close()


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _public_value(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    return value


def public_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "job_id": task.get("job_id"),
        "status": task.get("status"),
        "percent": int(task.get("percent") or 0),
        "message": task.get("message") or "",
        "result": _public_value(task.get("result")),
        "error": task.get("error"),
        "updated_at": task.get("updated_at"),
    }
