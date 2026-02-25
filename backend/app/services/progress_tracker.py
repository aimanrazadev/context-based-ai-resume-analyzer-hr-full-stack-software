import threading
import time
from typing import Any


_lock = threading.Lock()
_tasks: dict[str, dict[str, Any]] = {}


def create_task(*, task_id: str, user_id: int, job_id: int) -> None:
    now = time.time()
    with _lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "user_id": int(user_id),
            "job_id": int(job_id),
            "status": "running",  # running|done|error
            "percent": 0,
            "message": "Starting…",
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }


def update_task(*, task_id: str, percent: int | None = None, message: str | None = None) -> None:
    now = time.time()
    with _lock:
        t = _tasks.get(task_id)
        if not t or t.get("status") != "running":
            return
        if percent is not None:
            p = int(percent)
            if p < 0:
                p = 0
            if p > 99:
                p = 99
            t["percent"] = p
        if message is not None:
            t["message"] = str(message)
        t["updated_at"] = now


def complete_task(*, task_id: str, result: Any) -> None:
    now = time.time()
    with _lock:
        t = _tasks.get(task_id)
        if not t:
            return
        t["status"] = "done"
        t["percent"] = 100
        t["message"] = "Done"
        t["result"] = result
        t["error"] = None
        t["updated_at"] = now


def fail_task(*, task_id: str, error_message: str) -> None:
    now = time.time()
    with _lock:
        t = _tasks.get(task_id)
        if not t:
            return
        t["status"] = "error"
        t["error"] = str(error_message or "Failed")
        t["message"] = t["error"]
        # Keep whatever percent we had; clamp to < 100
        p = int(t.get("percent") or 0)
        if p >= 100:
            p = 99
        t["percent"] = p
        t["updated_at"] = now


def get_task(*, task_id: str) -> dict[str, Any] | None:
    with _lock:
        t = _tasks.get(task_id)
        return dict(t) if t else None


def public_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "job_id": task.get("job_id"),
        "status": task.get("status"),
        "percent": int(task.get("percent") or 0),
        "message": task.get("message") or "",
        "result": task.get("result"),
        "error": task.get("error"),
        "updated_at": task.get("updated_at"),
    }

