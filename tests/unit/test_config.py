import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.mcp_server.config import Settings


class TestSettings:
    def test_settings_default_values(self):
        settings = Settings()
        assert settings.db_mode == "neo4j"
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.neo4j_user == "neo4j"
        assert settings.docker_volume_name == "codebase_state_volume"

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

    def test_settings_from_env_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.mcp_server.config.load_dotenv"):
                settings = Settings.from_env()
                assert settings.neo4j_enabled is True
                assert settings.db_mode == "neo4j"
                assert settings.neo4j_password == ""
