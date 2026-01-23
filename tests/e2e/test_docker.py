from unittest.mock import MagicMock, patch

import pytest

import docker


class TestDockerIntegration:
    @pytest.fixture
    def mock_docker_client(self):
        with patch("docker.DockerClient") as mock:
            yield mock

    def test_dockerfile_exists(self):
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent.parent / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile should exist"

    def test_docker_compose_exists(self):
        from pathlib import Path

        compose_file = Path(__file__).parent.parent.parent / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml should exist"

    @patch("docker.DockerClient")
    def test_docker_build(self, mock_client):
        mock_client.return_value.images.build.return_value = MagicMock(id="test-image-id")
        mock_client.return_value.api.build.return_value = [
            {"stream": "Building..."},
            {"status": "Built"},
        ]

    def test_volume_creation(self):
        import os
        import tempfile

        from src.mcp_server.utils.init_manager import is_initialized, set_initialized

        with tempfile.TemporaryDirectory() as tmpdir:
            assert not is_initialized(tmpdir)
            assert set_initialized(tmpdir, True)
            assert is_initialized(tmpdir)
            assert set_initialized(tmpdir, False)
            assert not is_initialized(tmpdir)
