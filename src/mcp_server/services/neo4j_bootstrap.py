"""Helpers for resolving Neo4j connection settings at startup."""

from pathlib import Path

from ..config import Settings
from .neo4j_service_manager import ProjectNeo4jServiceManager


def prepare_neo4j_connection(settings: Settings, project_root: Path | None = None) -> Settings:
    """Resolve managed Neo4j connection details when auto-bootstrap is enabled."""
    if settings.db_mode != "neo4j" or settings.neo4j_bootstrap_mode != "auto":
        return settings

    resolved_project_root = (project_root or Path.cwd()).resolve()
    connection = ProjectNeo4jServiceManager(
        project_root=resolved_project_root,
        settings=settings,
    ).ensure_service()

    settings.neo4j_uri = connection.uri
    settings.neo4j_user = connection.user
    settings.neo4j_password = connection.password or ""
    settings.neo4j_auth_enabled = connection.auth_enabled
    return settings
