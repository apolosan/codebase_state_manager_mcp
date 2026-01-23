import difflib
import hashlib
import json
import os  # nosec: B404
import shutil
import signal  # nosec: B404
import subprocess  # nosec: B404
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..utils.validation import ValidationError, validate_path


class GitOperationError(Exception):
    """Exceção para erros em operações git."""

    pass


class GitTimeoutError(Exception):
    """Exceção para operações git que excederam o timeout."""

    pass


GIT_TIMEOUT_SECONDS = 30
GIT_COMMAND_TIMEOUT = 60

# Binary file extensions to ignore during file hashing and diff calculation
# Based on common binary extensions in software development and Linux
BINARY_EXTENSIONS = {
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".deb",
    ".rpm",
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".ico",
    ".svg",
    ".webp",
    ".avif",
    ".heic",
    # Audio/Video
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".mkv",
    ".wav",
    ".flac",
    ".aac",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    # Binaries/Executables
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".a",
    ".o",
    ".bin",
    ".out",
    ".app",
    # Java
    ".jar",
    ".class",
    ".war",
    ".ear",
    # Python
    ".pyc",
    ".pyo",
    ".pyd",
    # .NET
    ".dll",
    ".exe",  # repeated but ok
    # Databases
    ".db",
    ".sqlite",
    ".sqlite3",
    # Other binary formats
    ".iso",
    ".dmg",
    ".pkg",
    ".msi",
    ".cab",
    ".tgz",
    ".tbz2",
}


class GitManager:
    def __init__(self, repo_path: Optional[Path] = None) -> None:
        self.repo_path = repo_path

    def _run_git_command(
        self,
        args: list[str],
        cwd: Optional[Path] = None,
        timeout: int = GIT_COMMAND_TIMEOUT,
    ) -> subprocess.CompletedProcess:
        target_path = cwd or self.repo_path
        if target_path is None:
            raise GitOperationError("Nenhum repositório especificado")

        original_cwd = os.getcwd()
        try:
            os.chdir(target_path)
            result = subprocess.run(  # nosec: B603
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise GitOperationError(f"Git command failed: {' '.join(args)} - {error_msg}")
            return result
        except subprocess.TimeoutExpired:
            raise GitTimeoutError(f"Git command timed out after {timeout}s: {' '.join(args)}")
        except Exception as e:
            error_msg = str(e)
            if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                raise GitTimeoutError(f"Git command timed out after {timeout}s: {' '.join(args)}")
            raise GitOperationError(f"Git command failed: {' '.join(args)} - {error_msg}")
        finally:
            os.chdir(original_cwd)

    def get_current_branch(self, repo_path: Optional[Path] = None) -> str:
        target_path = repo_path or self.repo_path
        if target_path:
            result = self._run_git_command(
                ["git", "branch", "--show-current"],
                cwd=target_path,
            )
            stdout: str = result.stdout.strip()
            return stdout
        result = self._run_git_command(["git", "branch", "--show-current"])
        stdout = result.stdout.strip()
        return stdout

    def get_diff(self, commits: int = 3, repo_path: Optional[Path] = None) -> str:
        target_path = repo_path or self.repo_path
        if target_path is None:
            raise GitOperationError("Nenhum repositório especificado")

        result = self._run_git_command(
            ["git", "diff", f"HEAD~{commits}"],
            cwd=target_path,
        )
        diff_output: str = result.stdout.strip()
        return diff_output

    def get_working_diff(self, repo_path: Optional[Path] = None) -> str:
        """Get diff of working directory changes (unstaged + staged)."""
        target_path = repo_path or self.repo_path
        if target_path is None:
            raise GitOperationError("Nenhum repositório especificado")

        result = self._run_git_command(
            ["git", "diff"],
            cwd=target_path,
        )
        diff_output: str = result.stdout.strip()
        return diff_output

    def clone_to_volume(
        self, source_path: Path, volume_path: Path, exclude_gitignore: bool = True
    ) -> bool:
        import shutil

        try:
            validated_source = validate_path(str(source_path), source_path.parent)

            if volume_path.exists():
                shutil.rmtree(volume_path)

            shutil.copytree(
                validated_source,
                volume_path,
                ignore=shutil.ignore_patterns(".git") if exclude_gitignore else None,
            )
            return True
        except shutil.Error as e:
            raise GitOperationError(f"Failed to copy files: {e}")
        except ValidationError as e:
            raise GitOperationError(f"Invalid source path: {e}")
        except Exception as e:
            return False

    def init_repo(self, path: Path) -> bool:
        try:
            self._run_git_command(["git", "init"], cwd=path)
            self._run_git_command(
                ["git", "config", "user.email", "mcp@codebase.local"],
                cwd=path,
            )
            self._run_git_command(
                ["git", "config", "user.name", "Codebase State Manager"],
                cwd=path,
            )
            return True
        except (GitOperationError, GitTimeoutError):
            return False

    def create_branch(self, branch_name: str, repo_path: Optional[Path] = None) -> bool:
        target_path = repo_path or self.repo_path
        if not target_path:
            return False
        try:
            self._run_git_command(
                ["git", "checkout", "-b", branch_name],
                cwd=target_path,
            )
            return True
        except (GitOperationError, GitTimeoutError):
            return False

    def is_git_repo(self, path: Path) -> bool:
        try:
            git_path = path / ".git"
            return git_path.exists() and git_path.is_dir()
        except (OSError, ValueError):
            return False

    def get_directory_hashes(self, directory_path: Path) -> Dict[str, str]:
        """Compute SHA256 hash for each file in directory, excluding binary files."""
        file_hashes = {}
        for root, dirs, files in os.walk(directory_path):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != ".git"]
            for file in files:
                file_path = Path(root) / file

                # Skip binary files based on extension
                if file_path.suffix.lower() in BINARY_EXTENSIONS:
                    continue

                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                        relative_path = str(file_path.relative_to(directory_path))
                        file_hashes[relative_path] = file_hash
                except (OSError, ValueError):
                    continue
        return file_hashes

    def compute_changes_since_last_state(
        self,
        project_path: Path,
        last_state_file_hashes: Dict[str, str],
        volume_codebase_path: Optional[Path] = None,
        is_genesis: bool = False,
    ) -> Tuple[str, Dict[str, Optional[str]]]:
        """Compute changes between current project and last state.

        For genesis (state 0), returns full current hashes.
        For transitions, returns deltas: {file_path: new_hash} for changes/adds,
        {file_path: None} for deletions.
        """
        current_hashes = self.get_directory_hashes(project_path)

        if is_genesis:
            # For genesis, return full hashes
            delta_hashes = {path: hash_val for path, hash_val in current_hashes.items()}
        else:
            # For transitions, compute deltas
            delta_hashes = {}

            # Find changed/new files
            for file_path, current_hash in current_hashes.items():
                if (
                    file_path not in last_state_file_hashes
                    or last_state_file_hashes[file_path] != current_hash
                ):
                    delta_hashes[file_path] = current_hash

            # Find deleted files
            for file_path in last_state_file_hashes:
                if file_path not in current_hashes:
                    delta_hashes[file_path] = None  # type: ignore[assignment]  # Mark as deleted

        # Generate diff info based on changed files
        changed_files = []
        new_files = []
        deleted_files = []

        if not is_genesis:
            for file_path, current_hash in current_hashes.items():
                if file_path not in last_state_file_hashes:
                    new_files.append(file_path)
                elif last_state_file_hashes[file_path] != current_hash:
                    changed_files.append(file_path)

            for file_path in last_state_file_hashes:
                if file_path not in current_hashes:
                    deleted_files.append(file_path)
        else:
            # For genesis, all files are "new"
            new_files = list(current_hashes.keys())

        # Generate content diffs
        content_diffs = {}
        if volume_codebase_path and volume_codebase_path.exists() and not is_genesis:
            for file_path in changed_files:
                project_file = project_path / file_path
                volume_file = volume_codebase_path / file_path
                if (
                    project_file.exists()
                    and volume_file.exists()
                    and project_file.suffix.lower() not in BINARY_EXTENSIONS
                ):
                    try:
                        with open(volume_file, "r", encoding="utf-8", errors="ignore") as f:
                            old_content = f.read().splitlines(keepends=True)
                        with open(project_file, "r", encoding="utf-8", errors="ignore") as f:
                            new_content = f.read().splitlines(keepends=True)
                        diff = list(
                            difflib.unified_diff(
                                old_content,
                                new_content,
                                fromfile=file_path,
                                tofile=file_path,
                                lineterm="",
                            )
                        )
                        if diff:
                            content_diffs[file_path] = "\n".join(diff)
                    except Exception as e:
                        # Log and skip if can't read or diff
                        import logging

                        logging.getLogger(__name__).debug(f"Could not diff file {file_path}: {e}")

        if not is_genesis:
            for file_path in new_files:
                project_file = project_path / file_path
                if project_file.exists() and project_file.suffix.lower() not in BINARY_EXTENSIONS:
                    try:
                        with open(project_file, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if content:
                            content_diffs[file_path] = content
                    except Exception as e:
                        # Log and skip if can't read
                        import logging

                        logging.getLogger(__name__).debug(f"Could not read file {file_path}: {e}")

        diff_data = {
            "added": new_files,
            "modified": changed_files,
            "deleted": deleted_files,
            "content_diffs": content_diffs,
        }

        diff_info = json.dumps(diff_data)

        return diff_info, delta_hashes  # type: ignore[return-value]

    def sync_project_to_volume(
        self, source_path: Path, volume_path: Path, sync_git: bool = True
    ) -> bool:
        """Sync project files to volume."""
        # TODO: Implement proper sync
        return True
