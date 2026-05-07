"""Pytest configuration for integration tests."""

from __future__ import annotations

import gc
import json
import shutil
from pathlib import Path

import docker
import pytest

from src.mcp_server.config import Settings
from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
from src.mcp_server.services.neo4j_bootstrap import prepare_neo4j_connection


def _clear_neo4j_database(driver) -> None:
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture(autouse=True)
def cleanup_sqlite_connections():
    """Ensure all SQLite connections are closed after each test."""
    yield
    gc.collect()


@pytest.fixture(scope="session")
def managed_neo4j_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Start a managed Neo4j instance once for integration tests."""
    project_root = tmp_path_factory.mktemp("managed_neo4j_integration")
    client = docker.from_env()
    client.ping()

    settings = Settings(
        db_mode="neo4j",
        neo4j_bootstrap_mode="auto",
        neo4j_auth_enabled=False,
        neo4j_connection_timeout=90,
        sqlite_path=str(project_root / "test.db"),
    )
    resolved_settings = prepare_neo4j_connection(settings, project_root=project_root)

    yield resolved_settings

    runtime_file = project_root / ".data" / "neo4j" / "runtime.json"
    if runtime_file.exists():
        payload = json.loads(runtime_file.read_text())
        container_name = payload.get("container_name")
        if isinstance(container_name, str) and container_name:
            try:
                client.containers.get(container_name).remove(force=True)
            except Exception:
                pass
    shutil.rmtree(project_root / ".data" / "neo4j", ignore_errors=True)


@pytest.fixture
def managed_neo4j_repos(managed_neo4j_settings: Settings):
    """Provide clean Neo4j repositories backed by the managed integration instance."""
    state_repo, transition_repo = create_neo4j_repositories(
        uri=managed_neo4j_settings.neo4j_uri,
        user=managed_neo4j_settings.neo4j_user,
        password=managed_neo4j_settings.neo4j_password,
        settings=managed_neo4j_settings,
    )
    _clear_neo4j_database(state_repo.driver)

    try:
        yield state_repo, transition_repo
    finally:
        try:
            _clear_neo4j_database(state_repo.driver)
        finally:
            state_repo.driver.close()
