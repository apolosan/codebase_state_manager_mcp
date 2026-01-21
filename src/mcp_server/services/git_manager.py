import os
import subprocess
from pathlib import Path
from typing import Optional


class GitManager:
    def __init__(self, repo_path: Optional[Path] = None) -> None:
        self.repo_path = repo_path

    def get_current_branch(self) -> str:
        if self.repo_path:
            original_cwd = os.getcwd()
            try:
                os.chdir(self.repo_path)
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.strip()
            finally:
                os.chdir(original_cwd)
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_diff(
        self, commits: int = 3, repo_path: Optional[Path] = None
    ) -> str:
        target_path = repo_path or self.repo_path
        if target_path:
            original_cwd = os.getcwd()
            try:
                os.chdir(target_path)
                result = subprocess.run(
                    ["git", "diff", f"HEAD~{commits}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.strip()
            finally:
                os.chdir(original_cwd)
        result = subprocess.run(
            ["git", "diff", f"HEAD~{commits}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def clone_to_volume(
        self, source_path: Path, volume_path: Path, exclude_gitignore: bool = True
    ) -> bool:
        import shutil

        try:
            if volume_path.exists():
                shutil.rmtree(volume_path)
            shutil.copytree(
                source_path,
                volume_path,
                ignore=shutil.ignore_patterns(".git") if exclude_gitignore else None,
            )
            return True
        except Exception:
            return False

    def init_repo(self, path: Path) -> bool:
        original_cwd = os.getcwd()
        try:
            os.chdir(path)
            subprocess.run(
                ["git", "init"],
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "mcp@codebase.local"],
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Codebase State Manager"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except Exception:
            return False
        finally:
            os.chdir(original_cwd)

    def create_branch(self, branch_name: str, repo_path: Optional[Path] = None) -> bool:
        target_path = repo_path or self.repo_path
        if not target_path:
            return False
        original_cwd = os.getcwd()
        try:
            os.chdir(target_path)
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except Exception:
            return False
        finally:
            os.chdir(original_cwd)

    def is_git_repo(self, path: Path) -> bool:
        git_path = path / ".git"
        return git_path.exists() and git_path.is_dir()
