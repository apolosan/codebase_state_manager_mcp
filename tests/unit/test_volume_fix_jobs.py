from concurrent.futures import Future
from unittest.mock import Mock, patch


class TestVolumeFixJobs:
    def test_start_reuses_running_job_for_same_request(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        running_future = Future()
        with patch.object(manager, "_submit", return_value=running_future):
            first = manager.start(state_service, "/tmp/project")
            second = manager.start(state_service, "/tmp/project")

        assert first["job_id"] == second["job_id"]
        assert second["already_running"] is True

    def test_start_creates_new_job_after_finished_request(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        completed_future = Future()
        completed_future.set_result(
            {
                "success": True,
                "volume": {
                    "volume_path": "/tmp/volume",
                    "codebase_path": "/tmp/volume/codebase",
                    "current_state": 2,
                },
                "message": "Volume path reconstructed successfully",
            }
        )

        next_future = Future()

        with patch.object(manager, "_submit", side_effect=[completed_future, next_future]):
            first = manager.start(state_service, "/tmp/project")
            second = manager.start(state_service, "/tmp/project")

        assert first["job_id"] != second["job_id"]
        assert second["status"] in {"pending", "running"}
        assert second["already_running"] is False

    def test_get_result_returns_completed_payload_idempotently(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        completed_future = Future()
        completed_future.set_result(
            {
                "success": True,
                "volume": {
                    "volume_path": "/tmp/volume",
                    "codebase_path": "/tmp/volume/codebase",
                    "current_state": 2,
                },
                "message": "Volume path reconstructed successfully",
            }
        )

        with patch.object(manager, "_submit", return_value=completed_future):
            job = manager.start(state_service, "/tmp/project")

        first = manager.get_result(job["job_id"])
        second = manager.get_result(job["job_id"])

        assert first == second
        assert first["status"] == "completed"

    def test_get_status_returns_failed_for_job_exception(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        failed_future = Future()
        failed_future.set_exception(RuntimeError("boom"))

        with patch.object(manager, "_submit", return_value=failed_future):
            job = manager.start(state_service, "/tmp/project")

        status = manager.get_status(job["job_id"])

        assert status["status"] == "failed"
        assert "boom" in status["message"]

    def test_start_genesis_reuses_running_job_for_same_request(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        running_future = Future()
        with patch.object(manager, "_submit_genesis", return_value=running_future):
            first = manager.start_genesis(state_service, "/tmp/project", "/tmp/volume")
            second = manager.start_genesis(state_service, "/tmp/project", "/tmp/volume")

        assert first["job_id"] == second["job_id"]
        assert second["already_running"] is True

    def test_start_genesis_returns_completed_job_for_same_finished_request(self):
        from src.mcp_server.tools.volume_fix_jobs import VolumeFixJobManager

        manager = VolumeFixJobManager()
        state_service = Mock()

        completed_future = Future()
        completed_future.set_result(
            {
                "success": True,
                "state": {"state_number": 0},
                "message": "Genesis state created successfully",
            }
        )

        with patch.object(manager, "_submit_genesis", return_value=completed_future):
            first = manager.start_genesis(state_service, "/tmp/project", "/tmp/volume")

        second = manager.start_genesis(state_service, "/tmp/project", "/tmp/volume")

        assert first["job_id"] == second["job_id"]
        assert second["status"] == "completed"
        assert second["already_running"] is False
