"""Background job manager for idempotent VOLUME_PATH operations."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional


class VolumeFixJobManager:
    """Manage idempotent background jobs for volume operations."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="volume-fix")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._jobs_by_key: dict[str, str] = {}

    def _make_idempotency_key(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _make_fix_volume_path_key(self, state_service: Any, project_path: str) -> str:
        current_state = state_service.state_repo.get_current()
        current_state_number = getattr(current_state, "state_number", None)
        if not isinstance(current_state_number, int):
            current_state_number = None
        payload = {
            "operation": "fix_volume_path",
            "project_path": project_path,
            "volume_path": str(state_service.settings.docker_volume_name),
            "current_state": current_state_number,
        }
        return self._make_idempotency_key(payload)

    def _make_genesis_key(self, state_service: Any, project_path: str, volume_path: str) -> str:
        payload = {
            "operation": "genesis",
            "project_path": project_path,
            "volume_path": str(volume_path),
            "configured_volume_path": str(state_service.settings.docker_volume_name),
        }
        return self._make_idempotency_key(payload)

    def _submit(self, state_service: Any, project_path: str) -> Future:
        return self._executor.submit(self._run_fix_volume_path, state_service, project_path)

    def _submit_genesis(self, state_service: Any, project_path: str, volume_path: str) -> Future:
        return self._executor.submit(self._run_genesis, state_service, project_path, volume_path)

    def _run_fix_volume_path(self, state_service: Any, project_path: str) -> dict[str, Any]:
        success, volume, message = state_service.fix_volume_path(project_path)
        return {
            "success": success,
            "volume": volume,
            "message": message,
        }

    def _run_genesis(
        self, state_service: Any, project_path: str, volume_path: str
    ) -> dict[str, Any]:
        success, state, message = state_service.genesis(project_path, volume_path)
        return {
            "success": success,
            "state": state.to_dict() if state else None,
            "message": message,
        }

    def start(self, state_service: Any, project_path: str) -> dict[str, Any]:
        idempotency_key = self._make_fix_volume_path_key(state_service, project_path)

        with self._lock:
            existing_job_id = self._jobs_by_key.get(idempotency_key)
            if existing_job_id is not None:
                existing_job = self._jobs[existing_job_id]
                status = self._status_from_future(existing_job["future"])
                if status in {"pending", "running"}:
                    return {
                        "job_id": existing_job_id,
                        "status": status,
                        "message": "Reusing running volume path repair job",
                        "idempotency_key": idempotency_key,
                        "already_running": True,
                    }

                self._jobs_by_key.pop(idempotency_key, None)

            job_id = str(uuid.uuid4())
            future = self._submit(state_service, project_path)
            self._jobs[job_id] = {
                "future": future,
                "idempotency_key": idempotency_key,
                "project_path": project_path,
                "operation": "fix_volume_path",
            }
            self._jobs_by_key[idempotency_key] = job_id

            return {
                "job_id": job_id,
                "status": self._status_from_future(future),
                "message": "Volume path repair started",
                "idempotency_key": idempotency_key,
                "already_running": False,
            }

    def start_genesis(
        self,
        state_service: Any,
        project_path: str,
        volume_path: str,
    ) -> dict[str, Any]:
        idempotency_key = self._make_genesis_key(state_service, project_path, volume_path)

        with self._lock:
            existing_job_id = self._jobs_by_key.get(idempotency_key)
            if existing_job_id is not None:
                existing_job = self._jobs[existing_job_id]
                status = self._status_from_future(existing_job["future"])
                return {
                    "job_id": existing_job_id,
                    "status": status,
                    "message": (
                        "Reusing running genesis job"
                        if status in {"pending", "running"}
                        else "Reusing completed genesis job"
                    ),
                    "idempotency_key": idempotency_key,
                    "already_running": status in {"pending", "running"},
                }

            job_id = str(uuid.uuid4())
            future = self._submit_genesis(state_service, project_path, volume_path)
            self._jobs[job_id] = {
                "future": future,
                "idempotency_key": idempotency_key,
                "project_path": project_path,
                "volume_path": volume_path,
                "operation": "genesis",
            }
            self._jobs_by_key[idempotency_key] = job_id

            return {
                "job_id": job_id,
                "status": self._status_from_future(future),
                "message": "Genesis started",
                "idempotency_key": idempotency_key,
                "already_running": False,
            }

    def _status_from_future(self, future: Future) -> str:
        if future.running():
            return "running"
        if not future.done():
            return "pending"
        if future.exception() is not None:
            return "failed"
        return "completed"

    def get_status(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

        future = job["future"]
        status = self._status_from_future(future)
        message = "Volume path repair is still running"
        if status == "completed":
            result = future.result()
            message = result["message"]
        elif status == "failed":
            message = str(future.exception())

        return {
            "job_id": job_id,
            "status": status,
            "message": message,
            "idempotency_key": job["idempotency_key"],
        }

    def get_result(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

        future = job["future"]
        status = self._status_from_future(future)
        if status == "failed":
            return {
                "job_id": job_id,
                "status": "failed",
                "result": {
                    "success": False,
                    "volume": None,
                    "message": str(future.exception()),
                },
            }

        if status != "completed":
            return {
                "job_id": job_id,
                "status": status,
                "result": None,
            }

        return {
            "job_id": job_id,
            "status": "completed",
            "result": future.result(),
        }
