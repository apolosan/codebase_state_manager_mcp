import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import tempfile

from src.mcp_server.services.git_manager import GitManager


class TestGitManager:
    def test_git_manager_init(self):
        manager = GitManager()
        assert manager.repo_path is None

    def test_git_manager_with_path(self):
        manager = GitManager(Path("/test/path"))
        assert manager.repo_path == Path("/test/path")

    def test_is_git_repo_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            manager = GitManager(Path(tmpdir))
            assert manager.is_git_repo(Path(tmpdir)) is True

    def test_is_git_repo_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(Path(tmpdir))
            assert manager.is_git_repo(Path(tmpdir)) is False

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="main\n",
            returncode=0,
        )
        manager = GitManager()
        branch = manager.get_current_branch()
        assert branch == "main"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_diff(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="diff content\n",
            returncode=0,
        )
        manager = GitManager()
        diff = manager.get_diff(commits=1)
        assert diff == "diff content"
        mock_run.assert_called_once()
