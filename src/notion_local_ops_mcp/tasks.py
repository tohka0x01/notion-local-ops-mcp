from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TaskStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _task_dir(self, task_id: str) -> Path:
        return self.root / "tasks" / task_id

    def _meta_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "meta.json"

    def _stdout_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "stdout.log"

    def _stderr_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "stderr.log"

    def _summary_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "summary.txt"

    def _write_text(self, path: Path, content: str) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)

    def create(
        self,
        *,
        task: str,
        executor: str,
        cwd: str,
        timeout: int | None = None,
        context_files: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self._lock:
            task_id = uuid.uuid4().hex[:12]
            task_dir = self._task_dir(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "task_id": task_id,
                "task": task,
                "executor": executor,
                "cwd": cwd,
                "timeout": timeout,
                "context_files": context_files or [],
                "status": "queued",
                "created_at": _now(),
                "updated_at": _now(),
            }
            if metadata:
                payload.update(metadata)
            self._write_text(self._meta_path(task_id), json.dumps(payload, indent=2))
            self._write_text(self._stdout_path(task_id), "")
            self._write_text(self._stderr_path(task_id), "")
            self._write_text(self._summary_path(task_id), "")
            return payload

    def get(self, task_id: str) -> dict[str, object]:
        with self._lock:
            return json.loads(self._meta_path(task_id).read_text(encoding="utf-8"))

    def update(self, task_id: str, **fields: object) -> dict[str, object]:
        with self._lock:
            payload = self.get(task_id)
            payload.update(fields)
            payload["updated_at"] = _now()
            self._write_text(self._meta_path(task_id), json.dumps(payload, indent=2))
            return payload

    def write_logs(self, task_id: str, *, stdout: str, stderr: str) -> None:
        with self._lock:
            self._write_text(self._stdout_path(task_id), stdout)
            self._write_text(self._stderr_path(task_id), stderr)

    def write_summary(self, task_id: str, summary: str) -> None:
        with self._lock:
            self._write_text(self._summary_path(task_id), summary)

    def read_stdout(self, task_id: str) -> str:
        with self._lock:
            return self._stdout_path(task_id).read_text(encoding="utf-8")

    def read_stderr(self, task_id: str) -> str:
        with self._lock:
            return self._stderr_path(task_id).read_text(encoding="utf-8")

    def read_summary(self, task_id: str) -> str:
        with self._lock:
            return self._summary_path(task_id).read_text(encoding="utf-8").strip()
