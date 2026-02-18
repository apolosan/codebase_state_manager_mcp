"""Service for detecting current git branch with robust error handling."""

import logging
from pathlib import Path
from typing import Optional, cast

from ..models.state_model import BranchState
from ..utils.branch_utils import sanitize_branch_name

logger = logging.getLogger(__name__)


class BranchDetectionService:
    """Service responsible for detecting the current git branch.

    Handles all edge cases including:
    - Projects without git
    - Git errors
    - Detached HEAD state
    - Branch name sanitization
    """

    def __init__(self, git_manager=None):
        """Initialize the service.

        Args:
            git_manager: Optional git manager instance. If not provided,
                        will be imported internally.
        """
        if git_manager:
            self.git_manager = git_manager
        else:
            # Import here to avoid circular imports
            from src.mcp_server.services.git_manager import GitManager

            self.git_manager = GitManager()

    def get_current_branch_name(self, project_path: Path) -> str:
        """Get the current branch name from filesystem reality.

        This method ALWAYS queries the current filesystem state,
        never uses cached or stored values.

        Args:
            project_path: Path to the project directory.

        Returns:
            - Branch name (sanitized) if git repo with active branch
            - "not_versioned" if not a git repo
            - "git_error" if git operation failed
            - "detached_<hash>" if in detached HEAD state
            - "detached_head" if detached but hash unavailable
        """
        # Check if this is a git repository
        if not self.git_manager.is_git_repo(project_path):
            return cast(str, BranchState.NOT_VERSIONED.value)

        try:
            # Try to get current branch
            branch: str = self.git_manager.get_current_branch(repo_path=project_path)

            # Check if we're in detached HEAD state (empty branch name)
            if not branch or branch.strip() == "":
                return self._get_detached_head_identifier(project_path)

            # Sanitize and return branch name
            sanitized: str = sanitize_branch_name(branch)
            return sanitized

        except Exception as e:
            logger.warning(f"Git operation error getting branch for {project_path}: {e}")
            return cast(str, BranchState.GIT_ERROR.value)

    def _get_detached_head_identifier(self, project_path: Path) -> str:
        """Get identifier for detached HEAD state.

        Tries to get short hash of current commit for identification.

        Args:
            project_path: Path to project.

        Returns:
            "detached_<hash>" if hash available, "detached_head" otherwise.
        """
        try:
            result = self.git_manager._run_git_command(
                ["git", "rev-parse", "--short", "HEAD"], cwd=project_path
            )
            short_hash = result.stdout.strip()
            if short_hash:
                return f"detached_{short_hash}"
        except Exception as e:
            logger.debug(f"Could not get hash for detached HEAD: {e}")

        return cast(str, BranchState.DETACHED_HEAD.value)
