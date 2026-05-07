import shutil
from pathlib import Path

import docker
import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State
from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
from src.mcp_server.services.neo4j_bootstrap import prepare_neo4j_connection


class TestManagedNeo4jBootstrap:
    @pytest.fixture(autouse=True)
    def ensure_docker_available(self):
        client = docker.from_env()
        client.ping()

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            db_mode="neo4j",
            neo4j_bootstrap_mode="auto",
            neo4j_auth_enabled=False,
            neo4j_connection_timeout=90,
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def cleanup_managed_container(self, tmp_path):
        yield
        container_prefix = "codebase-state-manager-neo4j-"
        client = docker.from_env()
        for container in client.containers.list(all=True):
            if any(name.startswith(container_prefix) for name in container.name.split()):
                labels = container.labels or {}
                if labels.get("codebase-state-manager.project_root") == str(tmp_path.resolve()):
                    container.remove(force=True)
        shutil.rmtree(tmp_path / ".data" / "neo4j", ignore_errors=True)

    def test_prepare_neo4j_connection_bootstraps_project_scoped_container(
        self, settings, tmp_path, cleanup_managed_container
    ):
        resolved = prepare_neo4j_connection(settings, project_root=tmp_path)

        runtime_file = tmp_path / ".data" / "neo4j" / "runtime.json"
        assert resolved.neo4j_uri.startswith("bolt://127.0.0.1:")
        assert resolved.neo4j_auth_enabled is False
        assert runtime_file.exists()

    def test_managed_neo4j_persists_data_between_sessions(
        self, settings, tmp_path, cleanup_managed_container
    ):
        resolved_settings = prepare_neo4j_connection(settings, project_root=tmp_path)
        state_repo, transition_repo = create_neo4j_repositories(
            uri=resolved_settings.neo4j_uri,
            user=resolved_settings.neo4j_user,
            password=resolved_settings.neo4j_password,
            settings=resolved_settings,
        )

        state = State(
            state_number=0,
            user_prompt="Managed genesis",
            branch_name="main",
            git_diff_info="",
            hash="managed-hash-0",
        )
        assert state_repo.create(state) is True
        state_repo.set_metadata("current_state", "0")
        state_repo.driver.close()

        runtime_home = tmp_path / ".data" / "neo4j"
        assert (runtime_home / "data").exists()

        restarted_settings = Settings(
            db_mode="neo4j",
            neo4j_bootstrap_mode="auto",
            neo4j_auth_enabled=False,
            neo4j_connection_timeout=90,
            sqlite_path=str(tmp_path / "test.db"),
        )
        restarted_settings = prepare_neo4j_connection(restarted_settings, project_root=tmp_path)
        restarted_state_repo, restarted_transition_repo = create_neo4j_repositories(
            uri=restarted_settings.neo4j_uri,
            user=restarted_settings.neo4j_user,
            password=restarted_settings.neo4j_password,
            settings=restarted_settings,
        )

        recovered = restarted_state_repo.get_by_number(0)
        assert recovered is not None
        assert recovered.user_prompt == "Managed genesis"
        assert restarted_state_repo.get_metadata("current_state") == "0"
        restarted_state_repo.driver.close()
