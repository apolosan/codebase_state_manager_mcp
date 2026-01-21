"""
Docker Integration Tests for Codebase State Manager MCP Server.

These tests validate Docker build, containerization, and volume management.
"""

import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import tempfile
import shutil


class TestDockerBuild:
    """Tests for Docker image building."""

    @pytest.fixture
    def dockerfile_path(self):
        return Path(__file__).parent.parent.parent / "Dockerfile"

    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent.parent

    def test_dockerfile_exists(self, dockerfile_path):
        """Verify Dockerfile exists at project root."""
        assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"

    def test_dockerfile_has_base_image(self, dockerfile_path):
        """Verify Dockerfile uses python:3.10-slim base image."""
        content = dockerfile_path.read_text()
        assert "python:3.10-slim" in content, "Base image should be python:3.10-slim"

    def test_dockerfile_has_git_install(self, dockerfile_path):
        """Verify Git is installed in Dockerfile."""
        content = dockerfile_path.read_text()
        assert "git" in content.lower(), "Git should be installed"
        assert "apt-get" in content.lower() or "apt" in content.lower(), "apt-get should be used"

    def test_dockerfile_copies_requirements(self, dockerfile_path):
        """Verify requirements.txt is copied and installed."""
        content = dockerfile_path.read_text()
        assert "requirements.txt" in content, "requirements.txt should be copied"
        assert "pip install" in content.lower(), "pip install should be present"

    def test_dockerfile_exposes_port(self, dockerfile_path):
        """Verify port 8080 is exposed."""
        content = dockerfile_path.read_text()
        assert "EXPOSE" in content, "EXPOSE instruction should be present"
        assert "8080" in content, "Port 8080 should be exposed"

    def test_dockerfile_has_cmd(self, dockerfile_path):
        """Verify CMD instruction is present."""
        content = dockerfile_path.read_text()
        assert "CMD" in content, "CMD instruction should be present"


class TestDockerCompose:
    """Tests for Docker Compose configuration."""

    @pytest.fixture
    def compose_path(self):
        return Path(__file__).parent.parent.parent / "docker-compose.yml"

    def test_compose_file_exists(self, compose_path):
        """Verify docker-compose.yml exists."""
        assert compose_path.exists(), f"docker-compose.yml not found at {compose_path}"

    def test_compose_has_neo4j_service(self, compose_path):
        """Verify Neo4j service is defined."""
        content = compose_path.read_text()
        assert "neo4j" in content.lower(), "Neo4j service should be defined"
        assert "image: neo4j" in content or "neo4j:" in content, "Neo4j image should be specified"

    def test_compose_has_app_service(self, compose_path):
        """Verify app service is defined."""
        content = compose_path.read_text()
        assert "app:" in content or "services:" in content, "App service should be defined"

    def test_compose_defines_volumes(self, compose_path):
        """Verify volumes are defined."""
        content = compose_path.read_text()
        assert "volumes:" in content, "Volumes section should be present"

    def test_compose_has_depends_on(self, compose_path):
        """Verify app depends on neo4j."""
        content = compose_path.read_text()
        assert "depends_on" in content, "depends_on should be present for app service"


class TestVolumeManagement:
    """Tests for volume management functionality."""

    def test_volume_path_creation(self, tmp_path):
        """Test volume path creation."""
        from src.mcp_server.utils.init_manager import is_initialized, set_initialized
        
        volume_path = tmp_path / "test_volume"
        volume_path.mkdir()
        
        assert is_initialized(str(volume_path)) is False
        
        result = set_initialized(str(volume_path), True)
        assert result is True
        assert is_initialized(str(volume_path)) is True
        
        result = set_initialized(str(volume_path), False)
        assert result is True
        assert is_initialized(str(volume_path)) is False

    def test_volume_flag_file_location(self, tmp_path):
        """Test that flag file is created in correct location."""
        from src.mcp_server.utils.init_manager import is_initialized, set_initialized
        
        volume_path = tmp_path / "volume"
        volume_path.mkdir()
        
        set_initialized(str(volume_path), True)
        
        flag_file = volume_path / ".codebase_state_initialized"
        assert flag_file.exists(), "Flag file should be created in volume path"


class TestGitCloneToVolume:
    """Tests for git clone functionality."""

    def test_clone_excludes_git_directory(self, tmp_path):
        """Test that .git directory is excluded during clone."""
        from src.mcp_server.services.git_manager import GitManager

        source = tmp_path / "source"
        source.mkdir()
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("git config")
        (source / "file.txt").write_text("content")

        target = tmp_path / "target"

        manager = GitManager()
        result = manager.clone_to_volume(source, target, exclude_gitignore=True)

        assert result is True
        assert (target / "file.txt").exists(), "Regular files should be copied"
        assert not (target / ".git").exists(), ".git directory should be excluded"


class TestDockerEnvironmentVariables:
    """Tests for Docker environment variable configuration."""

    def test_settings_from_env_with_docker_defaults(self, tmp_path, monkeypatch):
        """Test that Settings loads correctly with Docker env vars."""
        from src.mcp_server.config import Settings
        
        monkeypatch.setenv("DB_MODE", "neo4j")
        monkeypatch.setenv("NEO4J_URI", "bolt://neo4j:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "docker_secret")
        monkeypatch.setenv("DOCKER_VOLUME_NAME", "test_volume")
        
        settings = Settings.from_env()
        
        assert settings.db_mode == "neo4j"
        assert settings.neo4j_uri == "bolt://neo4j:7687"
        assert settings.neo4j_user == "neo4j"
        assert settings.neo4j_password == "docker_secret"
        assert settings.docker_volume_name == "test_volume"


class TestDockerSecurity:
    """Security tests for Docker configuration."""

    def test_no_hardcoded_secrets_in_dockerfile(self):
        """Verify no hardcoded secrets in Dockerfile."""
        content = (Path(__file__).parent.parent.parent / "Dockerfile").read_text()
        
        assert "password" not in content.lower() or "ENV" not in content, \
            "Secrets should not be hardcoded in Dockerfile"

    def test_no_hardcoded_secrets_in_compose(self):
        """Verify no hardcoded secrets in docker-compose.yml."""
        content = (Path(__file__).parent.parent.parent / "docker-compose.yml").read_text()
        
        assert "password" not in content.lower() or "ENV" not in content, \
            "Secrets should not be hardcoded in docker-compose.yml"

    def test_dockerfile_uses_no_cache_for_pip(self):
        """Verify pip install uses --no-cache-dir."""
        content = (Path(__file__).parent.parent.parent / "Dockerfile").read_text()
        
        assert "--no-cache-dir" in content, \
            "pip install should use --no-cache-dir to reduce image size"
