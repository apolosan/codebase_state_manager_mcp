import difflib
import hashlib
import json
import os  # nosec: B404
import shutil
import signal  # nosec: B404
import subprocess  # nosec: B404
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ..utils.validation import ValidationError, validate_path

if TYPE_CHECKING:
    from ..utils.ignore_manager import IgnoreManager


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
    ".tgz",
    ".tbz2",
    ".txz",
    ".lz",
    ".lzma",
    ".lzo",
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
    ".heif",
    ".jp2",
    ".j2k",
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
    ".ogg",
    ".opus",
    ".m4a",
    ".m4v",
    ".webm",
    ".3gp",
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
    ".pyo",
    # .NET
    ".dll",
    ".exe",
    # Databases
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-journal",
    ".sqlite-wal",
    ".sqlite-shm",
    ".frm",
    ".myd",
    ".myi",
    ".ibd",
    # Cache and temporary files
    ".coverage",
    ".cache",
    ".swp",
    ".swo",
    ".tmp",
    ".temp",
    ".log",
    ".pid",
    ".lock",
    # Data serialization and models
    ".pkl",
    ".pickle",
    ".h5",
    ".hdf5",
    ".npy",
    ".npz",
    ".mat",
    ".data",
    ".model",
    ".weights",
    ".pt",
    ".pth",
    ".onnx",
    ".pb",
    ".tflite",
    ".mlmodel",
    ".joblib",
    ".sav",
    ".dat",
    ".idx",
    ".pack",  # Git objects
    # Other binary formats
    ".iso",
    ".dmg",
    ".pkg",
    ".msi",
    ".cab",
    ".img",
    ".toast",
    ".vcd",
    ".crx",
    ".xpi",
    ".whl",
    ".egg",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    # Virtual environments and environment files
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}

# Maximum file size to process (1MB)
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

# Directory and file patterns to ignore (similar to .gitignore)
# These patterns are checked against relative paths
IGNORE_PATTERNS = {
    # Version control directories
    ".git/",
    ".svn/",
    ".hg/",
    # Python cache and virtual environments
    "__pycache__/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".coverage",
    ".tox/",
    ".nox/",
    ".venv/",
    "venv/",
    "env/",
    ".env/",
    ".env.*",
    # Node.js
    "node_modules/",
    ".npm/",
    ".yarn/",
    # Build and distribution directories
    "build/",
    "dist/",
    "target/",
    "out/",
    ".next/",
    ".nuxt/",
    # IDE and editor files
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    # OS metadata
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    # Temporary files
    "*.tmp",
    "*.temp",
    "*.log",
    # Coverage and test results
    "coverage/",
    "htmlcov/",
    ".hypothesis/",
    # Database files (already in BINARY_EXTENSIONS but also ignore directories)
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Docker and volumes
    ".dockerignore",
    "Dockerfile",
    "docker-compose*.yml",
    "volumes/",
    # Neo4j data
    "neo4j/data/",
    "neo4j/logs/",
    # Specific to this project
    "data/",
    "mcp_data/",
    ".aim/",
    ".opencode/",
}


class GitManager:
    def __init__(self, repo_path: Optional[Path] = None) -> None:
        self.repo_path = repo_path

    def _should_ignore_path(
        self,
        relative_path: str,
        is_dir: bool,
        ignore_manager: Optional["IgnoreManager"] = None,
        project_path: Optional[Path] = None,
    ) -> bool:
        """Check if a path should be ignored based on ignore patterns and binary detection.

        Args:
            relative_path: Path relative to the directory being scanned
            is_dir: Whether the path is a directory
            ignore_manager: Optional IgnoreManager instance to use .gitignore patterns
            project_path: Path to project root (required if using ignore_manager)

        Returns:
            True if path should be ignored, False otherwise
        """
        import fnmatch
        import os

        # Normalize path separators to '/' for consistent pattern matching
        normalized_path = relative_path.replace(os.sep, "/")

        # Always ignore .git directory and anything inside it
        if ".git" in normalized_path.split("/"):
            return True

        # If ignore_manager and project_path are provided, use ignore_manager's logic
        if ignore_manager is not None and project_path is not None:
            try:
                ignore_func = ignore_manager.get_ignore_function(project_path)
                return ignore_func(relative_path, is_dir)
            except (OSError, IOError, ValueError, RuntimeError):
                # Fall back to default patterns if ignore_manager fails
                pass

        # Check ignore patterns
        for pattern in IGNORE_PATTERNS:
            # Patterns already use '/' as separator
            # Check if pattern matches the normalized path
            if fnmatch.fnmatch(normalized_path, pattern):
                return True
            # For directory patterns (ending with /), also match as directory component
            if pattern.endswith("/") and not is_dir:
                # Check if pattern (without trailing slash) appears as directory component
                pattern_dir = pattern.rstrip("/")
                if pattern_dir in normalized_path.split("/"):
                    return True

        # Check binary extensions for files
        if not is_dir:
            import os.path

            ext = os.path.splitext(relative_path)[1].lower()
            if ext in BINARY_EXTENSIONS:
                return True

        return False

    def _is_binary_file(self, file_path: Path) -> bool:
        """Detect if a file is binary by checking for null bytes or high non-ASCII ratio.

        Args:
            file_path: Path to the file

        Returns:
            True if file appears to be binary, False otherwise
        """
        try:
            # Quick check: file size too large
            if file_path.stat().st_size > MAX_FILE_SIZE:
                return True

            # Read first 8KB to check for null bytes
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return True

                # Check if chunk is valid UTF-8
                try:
                    chunk.decode("utf-8")
                except UnicodeDecodeError:
                    # High proportion of non-ASCII may indicate binary
                    non_ascii_count = sum(1 for byte in chunk if byte > 127)
                    if non_ascii_count > len(chunk) * 0.3:  # 30% threshold
                        return True
        except (OSError, IOError):
            # If we can't read, assume binary to be safe
            return True

        return False

    def _should_process_file(
        self,
        file_path: Path,
        relative_path: str,
        ignore_manager: Optional["IgnoreManager"] = None,
        project_path: Optional[Path] = None,
    ) -> bool:
        """Determine if a file should be processed for hashing and diffing.

        Args:
            file_path: Absolute path to the file
            relative_path: Relative path from project root
            ignore_manager: Optional IgnoreManager instance to use .gitignore patterns
            project_path: Path to project root (required if using ignore_manager)

        Returns:
            True if file should be processed, False if it should be ignored
        """
        # Check ignore patterns
        if self._should_ignore_path(
            relative_path, is_dir=False, ignore_manager=ignore_manager, project_path=project_path
        ):
            return False

        # Check binary detection
        if self._is_binary_file(file_path):
            return False

        return True

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
        self,
        source_path: Path,
        volume_path: Path,
        ignore_manager: Optional["IgnoreManager"] = None,
    ) -> bool:
        import shutil

        try:
            validated_source = validate_path(str(source_path), source_path.parent)

            if volume_path.exists():
                shutil.rmtree(volume_path)

            # Determine ignore function
            if ignore_manager is not None:
                custom_ignore = ignore_manager.get_ignore_function(source_path)

                def adapter_ignore(dir_path: str, files: list[str]) -> list[str]:
                    """Adapter function for shutil.copytree ignore parameter."""
                    ignored = []
                    for filename in files:
                        full_path = os.path.join(dir_path, filename)
                        rel_path = os.path.relpath(full_path, str(validated_source))

                        # Check if file/directory should be ignored
                        is_dir = os.path.isdir(full_path)
                        if custom_ignore(rel_path, is_dir):
                            ignored.append(filename)
                    return ignored

                ignore_func = adapter_ignore
            else:
                # Fallback to basic .git ignore for backward compatibility
                ignore_func = shutil.ignore_patterns(".git")  # type: ignore[assignment]

            shutil.copytree(
                validated_source,
                volume_path,
                ignore=ignore_func,
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

    def get_directory_hashes(
        self, directory_path: Path, ignore_manager: Optional["IgnoreManager"] = None
    ) -> Dict[str, str]:
        """Compute SHA256 hash for each file in directory, excluding binary and ignored files.

        Args:
            directory_path: Path to directory to scan
            ignore_manager: Optional IgnoreManager instance to use .gitignore patterns

        Returns:
            Dictionary mapping relative file paths to SHA256 hashes
        """
        file_hashes = {}
        for root, dirs, files in os.walk(directory_path):
            # Filter directories using ignore patterns
            dirs[:] = [
                d
                for d in dirs
                if not self._should_ignore_path(
                    str(Path(root).relative_to(directory_path) / d),
                    is_dir=True,
                    ignore_manager=ignore_manager,
                    project_path=directory_path,
                )
            ]

            for file in files:
                file_path = Path(root) / file
                relative_path = str(file_path.relative_to(directory_path))

                # Check if file should be processed
                if not self._should_process_file(
                    file_path,
                    relative_path,
                    ignore_manager=ignore_manager,
                    project_path=directory_path,
                ):
                    continue

                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
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
        ignore_manager: Optional["IgnoreManager"] = None,
    ) -> Tuple[str, Dict[str, Optional[str]]]:
        """Compute changes between current project and last state.

        For genesis (state 0), returns full current hashes.
        For transitions, returns deltas: {file_path: new_hash} for changes/adds,
        {file_path: None} for deletions.
        """
        current_hashes = self.get_directory_hashes(project_path, ignore_manager=ignore_manager)

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
                    and self._should_process_file(
                        project_file,
                        file_path,
                        ignore_manager=ignore_manager,
                        project_path=project_path,
                    )
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
                if project_file.exists() and self._should_process_file(
                    project_file,
                    file_path,
                    ignore_manager=ignore_manager,
                    project_path=project_path,
                ):
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
