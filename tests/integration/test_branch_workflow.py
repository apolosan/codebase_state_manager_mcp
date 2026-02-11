"""End-to-end integration tests for branch detection workflow."""

import shutil
import subprocess
from pathlib import Path

import pytest


class TestBranchDetectionWorkflow:
    """Test complete workflows with branch changes."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        return tmp_path

    def test_workflow_multiple_branch_changes(self, temp_project):
        """Test workflow with multiple branch transitions."""
        from src.mcp_server.services.branch_detection_service import (
            BranchDetectionService,
        )

        service = BranchDetectionService()

        # 1. Inicializar git
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=temp_project,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_project,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_project,
            capture_output=True,
        )

        # Criar commit inicial
        (temp_project / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=temp_project, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=temp_project,
            capture_output=True,
        )

        # Estado 1: main
        branch1 = service.get_current_branch_name(temp_project)
        assert branch1 == "main"

        # 2. Criar e mudar para feature-x
        subprocess.run(
            ["git", "checkout", "-b", "feature-x"],
            cwd=temp_project,
            capture_output=True,
        )

        # Estado 2: feature-x
        branch2 = service.get_current_branch_name(temp_project)
        assert branch2 == "feature-x"

        # 3. Mudar para develop
        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=temp_project,
            capture_output=True,
        )

        # Estado 3: develop
        branch3 = service.get_current_branch_name(temp_project)
        assert branch3 == "develop"

        # 4. Checkout de commit específico (detached HEAD)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_project,
            capture_output=True,
            text=True,
        )
        commit_hash = result.stdout.strip()
        subprocess.run(
            ["git", "checkout", commit_hash],
            cwd=temp_project,
            capture_output=True,
        )

        # Estado 4: detached
        branch4 = service.get_current_branch_name(temp_project)
        assert branch4.startswith("detached_")

        # 5. Remover .git
        shutil.rmtree(temp_project / ".git")

        # Estado 5: not_versioned
        branch5 = service.get_current_branch_name(temp_project)
        assert branch5 == "not_versioned"
