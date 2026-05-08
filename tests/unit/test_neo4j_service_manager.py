import json
from unittest.mock import Mock, patch

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.services.neo4j_service_manager import (
    ManagedNeo4jConnection,
    Neo4jServiceError,
    ProjectNeo4jServiceManager,
)


def _make_container(status: str, bolt_port: int, http_port: int) -> Mock:
    container = Mock()
    container.status = status
    container.attrs = {
        "NetworkSettings": {
            "Ports": {
                "7687/tcp": [{"HostPort": str(bolt_port)}],
                "7474/tcp": [{"HostPort": str(http_port)}],
            }
        }
    }
    return container


class TestProjectNeo4jServiceManager:
    def test_build_runtime_state_is_project_scoped_and_deterministic(self, tmp_path):
        settings = Settings(db_mode="neo4j", neo4j_bootstrap_mode="auto")
        manager = ProjectNeo4jServiceManager(project_root=tmp_path, settings=settings)

        runtime_state = manager._build_runtime_state()

        assert runtime_state.container_name.startswith("codebase-state-manager-neo4j-")
        assert runtime_state.runtime_file == tmp_path / ".data" / "neo4j" / "runtime.json"
        assert runtime_state.data_dir == tmp_path / ".data" / "neo4j" / "data"
        assert runtime_state.logs_dir == tmp_path / ".data" / "neo4j" / "logs"
        assert runtime_state.image == "neo4j:5.24"
        assert runtime_state.auth_enabled is False

    def test_ensure_service_creates_authless_container_and_persists_runtime(self, tmp_path):
        client = Mock()
        client.ping.return_value = True
        client.containers.list.return_value = []
        client.containers.run.return_value = _make_container("running", 17687, 17474)

        settings = Settings(db_mode="neo4j", neo4j_bootstrap_mode="auto")
        manager = ProjectNeo4jServiceManager(
            project_root=tmp_path,
            settings=settings,
            client_factory=lambda: client,
        )

        with (
            patch.object(manager, "_find_available_port", side_effect=[17687, 17474]),
            patch.object(manager, "_wait_until_ready"),
        ):
            connection = manager.ensure_service()

        run_kwargs = client.containers.run.call_args.kwargs
        assert run_kwargs["environment"]["NEO4J_AUTH"] == "none"
        assert run_kwargs["ports"]["7687/tcp"] == 17687
        assert run_kwargs["ports"]["7474/tcp"] == 17474
        assert connection.uri == "bolt://127.0.0.1:17687"
        assert connection.auth_enabled is False

        runtime_payload = json.loads((tmp_path / ".data" / "neo4j" / "runtime.json").read_text())
        assert runtime_payload["container_name"] == connection.container_name
        assert runtime_payload["bolt_port"] == 17687
        assert runtime_payload["http_port"] == 17474
        assert runtime_payload["auth_enabled"] is False

    def test_ensure_service_reuses_existing_container_from_persisted_runtime(self, tmp_path):
        client = Mock()
        client.ping.return_value = True
        container = _make_container("exited", 18687, 18474)
        client.containers.list.return_value = [container]

        settings = Settings(db_mode="neo4j", neo4j_bootstrap_mode="auto")
        manager = ProjectNeo4jServiceManager(
            project_root=tmp_path,
            settings=settings,
            client_factory=lambda: client,
        )
        runtime_state = manager._build_runtime_state()
        runtime_state.bolt_port = 18687
        runtime_state.http_port = 18474
        manager._persist_runtime_state(runtime_state)

        with patch.object(manager, "_wait_until_ready"):
            connection = manager.ensure_service()

        container.start.assert_called_once()
        client.containers.run.assert_not_called()
        assert connection.uri == "bolt://127.0.0.1:18687"

    def test_ensure_service_recreates_missing_container_from_saved_runtime(self, tmp_path):
        client = Mock()
        client.ping.return_value = True
        client.containers.list.return_value = []
        client.containers.run.return_value = _make_container("running", 19687, 19474)

        settings = Settings(db_mode="neo4j", neo4j_bootstrap_mode="auto")
        manager = ProjectNeo4jServiceManager(
            project_root=tmp_path,
            settings=settings,
            client_factory=lambda: client,
        )
        runtime_state = manager._build_runtime_state()
        runtime_state.bolt_port = 19687
        runtime_state.http_port = 19474
        manager._persist_runtime_state(runtime_state)

        with patch.object(manager, "_wait_until_ready"):
            connection = manager.ensure_service()

        run_kwargs = client.containers.run.call_args.kwargs
        assert run_kwargs["name"] == runtime_state.container_name
        assert run_kwargs["ports"]["7687/tcp"] == 19687
        assert run_kwargs["ports"]["7474/tcp"] == 19474
        assert connection.uri == "bolt://127.0.0.1:19687"

    def test_wait_until_ready_uses_short_connectivity_probes(self, tmp_path):
        settings = Settings(
            db_mode="neo4j", neo4j_bootstrap_mode="auto", neo4j_connection_timeout=90
        )
        manager = ProjectNeo4jServiceManager(
            project_root=tmp_path,
            settings=settings,
            sleep_func=lambda _: None,
        )
        connection = ManagedNeo4jConnection(
            uri="bolt://127.0.0.1:17687",
            user="",
            password=None,
            auth_enabled=False,
            container_name="codebase-state-manager-neo4j-test",
            bolt_port=17687,
            http_port=17474,
            data_dir=tmp_path / ".data" / "neo4j" / "data",
            logs_dir=tmp_path / ".data" / "neo4j" / "logs",
            runtime_file=tmp_path / ".data" / "neo4j" / "runtime.json",
            image="neo4j:5.24",
        )
        first_driver = Mock()
        first_driver.verify_connectivity.side_effect = RuntimeError("not ready")
        second_driver = Mock()

        with (
            patch(
                "src.mcp_server.services.neo4j_service_manager.GraphDatabase.driver",
                side_effect=[first_driver, second_driver],
            ) as driver_factory,
            patch(
                "src.mcp_server.services.neo4j_service_manager.time.monotonic",
                side_effect=[0.0, 0.0, 1.0, 1.0],
            ),
        ):
            manager._wait_until_ready(connection)

        expected_probe_timeout = 5.0
        assert (
            driver_factory.call_args_list[0].kwargs["connection_timeout"] == expected_probe_timeout
        )
        assert (
            driver_factory.call_args_list[0].kwargs["connection_acquisition_timeout"]
            == expected_probe_timeout
        )
        first_driver.verify_connectivity.assert_called_once_with()
        second_driver.verify_connectivity.assert_called_once_with()

    def test_wait_until_ready_reports_last_probe_error_after_timeout(self, tmp_path):
        settings = Settings(
            db_mode="neo4j", neo4j_bootstrap_mode="auto", neo4j_connection_timeout=3
        )
        manager = ProjectNeo4jServiceManager(
            project_root=tmp_path,
            settings=settings,
            sleep_func=lambda _: None,
        )
        connection = ManagedNeo4jConnection(
            uri="bolt://127.0.0.1:17687",
            user="",
            password=None,
            auth_enabled=False,
            container_name="codebase-state-manager-neo4j-test",
            bolt_port=17687,
            http_port=17474,
            data_dir=tmp_path / ".data" / "neo4j" / "data",
            logs_dir=tmp_path / ".data" / "neo4j" / "logs",
            runtime_file=tmp_path / ".data" / "neo4j" / "runtime.json",
            image="neo4j:5.24",
        )
        failing_driver = Mock()
        failing_driver.verify_connectivity.side_effect = RuntimeError("still booting")

        with (
            patch(
                "src.mcp_server.services.neo4j_service_manager.GraphDatabase.driver",
                return_value=failing_driver,
            ),
            patch(
                "src.mcp_server.services.neo4j_service_manager.time.monotonic",
                side_effect=[0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.1],
            ),
            pytest.raises(Neo4jServiceError, match="still booting"),
        ):
            manager._wait_until_ready(connection)
