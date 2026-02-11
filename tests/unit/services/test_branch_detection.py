"""Tests for branch detection service."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestBranchState:
    """Tests for BranchState enum."""

    def test_branch_state_values_exist(self):
        """Test that all branch state values are defined."""
        from src.mcp_server.models.state_model import BranchState

        assert BranchState.NOT_VERSIONED == "not_versioned"
        assert BranchState.GIT_ERROR == "git_error"
        assert BranchState.DETACHED_HEAD == "detached_head"

    def test_branch_state_is_string_enum(self):
        """Test that BranchState is a string enum."""
        from src.mcp_server.models.state_model import BranchState

        assert isinstance(BranchState.NOT_VERSIONED, str)
        assert BranchState.NOT_VERSIONED.value == "not_versioned"


class TestSanitizeBranchName:
    """Tests for branch name sanitization."""

    def test_sanitize_normal_branch(self):
        """Test sanitizing a normal branch name."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        result = sanitize_branch_name("main")
        assert result == "main"

    def test_sanitize_branch_with_slashes(self):
        """Test sanitizing branch with slashes."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        result = sanitize_branch_name("feature/new-feature")
        assert result == "feature_new-feature"

    def test_sanitize_branch_with_special_chars(self):
        """Test sanitizing branch with special characters."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        result = sanitize_branch_name("feature/test_123-ABC")
        assert result == "feature_test_123-ABC"

    def test_sanitize_long_branch_name(self):
        """Test sanitizing very long branch name."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        long_name = "a" * 300
        result = sanitize_branch_name(long_name)
        assert len(result) <= 255
        assert result == "a" * 255

    def test_sanitize_empty_branch(self):
        """Test sanitizing empty branch name."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        result = sanitize_branch_name("")
        assert result == ""

    def test_sanitize_branch_with_unicode(self):
        """Test sanitizing branch with unicode characters."""
        from src.mcp_server.utils.branch_utils import sanitize_branch_name

        result = sanitize_branch_name("feature/🔥-hotfix")
        assert "🔥" not in result  # Emoji should be removed or replaced


class TestBranchDetectionService:
    """Test suite for BranchDetectionService."""

    @pytest.fixture
    def branch_service(self, tmp_path):
        """Create BranchDetectionService with mocked git manager."""
        from src.mcp_server.services.branch_detection_service import (
            BranchDetectionService,
        )

        return BranchDetectionService()

    def test_get_branch_with_git_normal(self, branch_service, tmp_path):
        """Caso 1A: Branch normal com git."""
        # Setup: Criar repo git mock
        git_manager = Mock()
        git_manager.is_git_repo.return_value = True
        git_manager.get_current_branch.return_value = "main"
        branch_service.git_manager = git_manager

        result = branch_service.get_current_branch_name(tmp_path)

        assert result == "main"
        git_manager.is_git_repo.assert_called_once_with(tmp_path)
        git_manager.get_current_branch.assert_called_once_with(repo_path=tmp_path)

    def test_get_branch_without_git(self, branch_service, tmp_path):
        """Caso 2: Projeto sem git."""
        git_manager = Mock()
        git_manager.is_git_repo.return_value = False
        branch_service.git_manager = git_manager

        result = branch_service.get_current_branch_name(tmp_path)

        assert result == "not_versioned"

    def test_get_branch_git_error(self, branch_service, tmp_path):
        """Caso 3: Git com erro."""
        git_manager = Mock()
        git_manager.is_git_repo.return_value = True
        git_manager.get_current_branch.side_effect = Exception("Git error")
        branch_service.git_manager = git_manager

        result = branch_service.get_current_branch_name(tmp_path)

        assert result == "git_error"

    def test_get_branch_detached_head(self, branch_service, tmp_path):
        """Caso 4: Detached HEAD - branch vazia."""
        git_manager = Mock()
        git_manager.is_git_repo.return_value = True
        git_manager.get_current_branch.return_value = ""

        # Mock para _run_git_command
        mock_result = Mock()
        mock_result.stdout = "a1b2c3d\n"
        git_manager._run_git_command.return_value = mock_result

        branch_service.git_manager = git_manager

        result = branch_service.get_current_branch_name(tmp_path)

        assert result == "detached_a1b2c3d"

    def test_get_branch_detached_head_no_hash(self, branch_service, tmp_path):
        """Caso 4b: Detached HEAD - sem hash disponível."""
        git_manager = Mock()
        git_manager.is_git_repo.return_value = True
        git_manager.get_current_branch.return_value = ""
        git_manager._run_git_command.side_effect = Exception("No hash")
        branch_service.git_manager = git_manager

        result = branch_service.get_current_branch_name(tmp_path)

        assert result == "detached_head"


class TestBranchTransitions:
    """Tests for branch state transitions using real git."""

    @pytest.fixture
    def branch_service(self):
        from src.mcp_server.services.branch_detection_service import (
            BranchDetectionService,
        )

        return BranchDetectionService()

    def test_transition_git_to_no_git(self, branch_service, tmp_path):
        """Caso 5A: Transição com git → sem git."""
        import shutil
        import subprocess

        # Setup: Criar repo git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Verificar que detecta branch
        result1 = branch_service.get_current_branch_name(tmp_path)
        assert result1 == "main"

        # Remover .git
        shutil.rmtree(tmp_path / ".git")

        # Verificar que detecta not_versioned
        result2 = branch_service.get_current_branch_name(tmp_path)
        assert result2 == "not_versioned"

    def test_transition_no_git_to_git(self, branch_service, tmp_path):
        """Caso 5B: Transição sem git → com git."""
        import subprocess

        # Setup: Sem git
        result1 = branch_service.get_current_branch_name(tmp_path)
        assert result1 == "not_versioned"

        # Inicializar git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Verificar que detecta branch
        result2 = branch_service.get_current_branch_name(tmp_path)
        assert result2 == "main"

    def test_transition_branch_change(self, branch_service, tmp_path):
        """Caso 5C: Mudança de branch."""
        import subprocess

        # Setup: Criar repo com duas branches
        # Use --initial-branch=main para garantir nome consistente
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Criar commit e branches
        (tmp_path / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feature-x"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Verificar branch atual
        result = branch_service.get_current_branch_name(tmp_path)
        assert result == "feature-x"

        # Mudar para main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Verificar mudança
        result2 = branch_service.get_current_branch_name(tmp_path)
        assert result2 == "main"
