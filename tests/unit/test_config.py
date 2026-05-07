import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.mcp_server.config import Settings


class TestSettings:
    def test_settings_default_values(self):
        settings = Settings()
        expected_volume_path = str(
            Path("/opt/codebase-state-manager/volumes") / Path.cwd().resolve().name
        )
        assert settings.db_mode == "neo4j"
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.neo4j_user == "neo4j"
        assert settings.neo4j_bootstrap_mode == "auto"
        assert settings.neo4j_auth_enabled is False
        assert settings.neo4j_auto_image == "neo4j:5.24"
        assert settings.docker_volume_name == expected_volume_path
        assert settings.volume_path == expected_volume_path

    def test_settings_custom_values(self):
        settings = Settings(
            db_mode="sqlite",
            neo4j_uri="bolt://custom:7687",
            neo4j_user="admin",
            neo4j_password="secret",
            sqlite_path="/custom/path.db",
        )
        assert settings.db_mode == "sqlite"
        assert settings.neo4j_uri == "bolt://custom:7687"
        assert settings.neo4j_user == "admin"
        assert settings.neo4j_password == "secret"
        assert settings.sqlite_path == "/custom/path.db"

    def test_settings_to_dict(self):
        settings = Settings(neo4j_password="secret")
        result = settings.to_dict()
        assert result["neo4j_password"] == "***"
        assert result["db_mode"] == "neo4j"
        assert result["neo4j_bootstrap_mode"] == settings.neo4j_bootstrap_mode

    def test_settings_from_env_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.mcp_server.config.load_dotenv"):
                settings = Settings.from_env()
                expected_volume_path = str(
                    Path("/opt/codebase-state-manager/volumes") / Path.cwd().resolve().name
                )
                assert settings.neo4j_enabled is True
                assert settings.db_mode == "neo4j"
                assert settings.neo4j_password == ""
                assert settings.neo4j_bootstrap_mode == "auto"
                assert settings.neo4j_auth_enabled is False
                assert settings.volume_path == expected_volume_path
                assert settings.docker_volume_name == expected_volume_path

    def test_settings_from_env_explicit_neo4j_config_uses_external_mode(self):
        env = {
            "DB_MODE": "neo4j",
            "NEO4J_URI": "bolt://neo4j.example:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "secret",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("src.mcp_server.config.load_dotenv"):
                settings = Settings.from_env()
                assert settings.neo4j_bootstrap_mode == "external"
                assert settings.neo4j_auth_enabled is True
                assert settings.neo4j_uri == "bolt://neo4j.example:7687"
                assert settings.neo4j_password == "secret"

    def test_settings_from_env_uses_opt_fallback_named_after_project_directory(self, tmp_path, monkeypatch):
        project_root = tmp_path / "my-project"
        project_root.mkdir()
        monkeypatch.chdir(project_root)

        with patch.dict(os.environ, {}, clear=True):
            with patch("src.mcp_server.config.load_dotenv"):
                settings = Settings.from_env()

        expected_volume_path = "/opt/codebase-state-manager/volumes/my-project"
        assert settings.volume_path == expected_volume_path
        assert settings.docker_volume_name == expected_volume_path

    def test_settings_syncs_volume_path_from_explicit_docker_volume_name(self, tmp_path):
        explicit_volume = str(tmp_path / "managed-volume")

        settings = Settings(docker_volume_name=explicit_volume)

        assert settings.docker_volume_name == explicit_volume
        assert settings.volume_path == explicit_volume
