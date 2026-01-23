"""
Ignore management system for genesis_tool directory copying.

This module provides intelligent directory filtering for the codebase state manager,
supporting both .gitignore-based patterns and fallback ignore rules for different
project types.
"""

import fnmatch
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set


class ProjectDetector:
    """Detects project type from characteristic files in the project root."""

    # Project type indicators (filename -> project_type)
    PROJECT_INDICATORS = {
        "package.json": "nodejs",
        "pyproject.toml": "python",
        "poetry.lock": "python",
        "requirements.txt": "python",
        "setup.py": "python",
        "Pipfile": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "java",
        "build.gradle": "java",
        "build.gradle.kts": "java",
        "Package.swift": "swift",
        "project.json": "dotnet",
        "*.csproj": "dotnet",
        "*.fsproj": "dotnet",
        "*.vbproj": "dotnet",
        "composer.json": "php",
        "Gemfile": "ruby",
        "Makefile": "c",
        "configure.ac": "c",
        "CMakeLists.txt": "cpp",
    }

    @staticmethod
    def detect_project_type(project_path: Path) -> str:
        """
        Detect project type by examining files in the project root.

        Args:
            project_path: Path to the project root directory

        Returns:
            Project type string (e.g., 'nodejs', 'python', 'java', etc.)
            or 'unknown' if type cannot be determined
        """
        if not project_path.exists() or not project_path.is_dir():
            return "unknown"

        # Check for exact filename matches
        for indicator_file, project_type in ProjectDetector.PROJECT_INDICATORS.items():
            if "*" not in indicator_file:
                if (project_path / indicator_file).exists():
                    return project_type

        # Check for glob patterns
        for indicator_file, project_type in ProjectDetector.PROJECT_INDICATORS.items():
            if "*" in indicator_file:
                for file_path in project_path.glob(indicator_file):
                    if file_path.exists():
                        return project_type

        return "unknown"


class GitignoreParser:
    """Parses .gitignore files into ignore patterns."""

    @staticmethod
    def parse_gitignore(gitignore_path: Path) -> List[str]:
        """
        Parse a .gitignore file and return a list of patterns.

        Supports full .gitignore syntax including:
        - Wildcards (*, ?, [])
        - Directory markers (/)
        - Negation (!)
        - Comments (#)

        Args:
            gitignore_path: Path to the .gitignore file

        Returns:
            List of ignore patterns, or empty list if file doesn't exist or is invalid
        """
        patterns: List[str] = []

        if not gitignore_path.exists():
            return patterns

        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Remove trailing whitespace and directory markers for processing
                    pattern = line.rstrip()

                    # Skip empty patterns after processing
                    if not pattern:
                        continue

                    patterns.append(pattern)

        except (OSError, UnicodeDecodeError):
            # Return empty list on any file reading error
            return []

        return patterns

    @staticmethod
    def create_ignore_function(patterns: List[str]) -> Callable[[str, bool], bool]:
        """
        Create an ignore function compatible with shutil.copytree.

        Args:
            patterns: List of .gitignore-style patterns

        Returns:
            Function that returns True if path should be ignored
        """

        def should_ignore(path: str, is_dir: bool) -> bool:
            """
            Determine if a path should be ignored based on patterns.

            Args:
                path: Relative path from copy root
                is_dir: Whether the path is a directory

            Returns:
                True if path should be ignored, False otherwise
            """
            # Always ignore .git directory and anything inside it
            path_parts = path.split("/")
            if ".git" in path_parts:
                return True

            # Check each pattern
            for pattern in patterns:
                if GitignoreParser._matches_pattern(path, pattern, is_dir):
                    return True

            return False

        return should_ignore

    @staticmethod
    def _matches_pattern(path: str, pattern: str, is_dir: bool) -> bool:
        """
        Check if a path matches a .gitignore pattern.

        Simplified implementation supporting basic .gitignore syntax:
        - Wildcards (*, ?, [])
        - Directory markers (/)
        - Basic negation handling

        Args:
            path: Path to check
            pattern: .gitignore pattern
            is_dir: Whether path is a directory

        Returns:
            True if pattern matches path
        """
        # Handle negation (patterns starting with !)
        if pattern.startswith("!"):
            # Negation patterns are not supported in this simplified implementation
            # They would require two-pass processing
            return False

        # Normalize path separators
        path = path.replace(os.sep, "/")

        # Handle directory-only patterns (ending with /)
        is_directory_pattern = pattern.endswith("/")
        if is_directory_pattern:
            pattern = pattern[:-1]

        # Handle patterns starting with /
        if pattern.startswith("/"):
            # Rooted patterns only match from root
            pattern = pattern[1:]
            if "/" in path:
                return False

        # Use fnmatch for glob matching
        import re

        # Convert glob pattern to regex
        regex_pattern = fnmatch.translate(pattern)

        # Check if the path itself matches
        if re.match(regex_pattern, path, re.IGNORECASE):
            # For directory patterns, only match if it's actually a directory
            if is_directory_pattern and not is_dir:
                return False
            return True

        # For directory patterns, check if path is inside the directory
        if is_directory_pattern:
            escaped_pattern = re.escape(pattern + "/")
            if re.match(f"{escaped_pattern}.*", path, re.IGNORECASE):
                return True

        return False


class IgnoreManager:
    """Main entry point for ignore logic management."""

    # Default ignore patterns by project type
    DEFAULT_IGNORES = {
        "nodejs": [
            "node_modules/",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
            ".npm",
            "coverage/",
            "dist/",
            "build/",
            ".next/",
            ".nuxt/",
            ".vuepress/dist",
            ".cache/",
            ".parcel-cache/",
            ".nyc_output",
        ],
        "python": [
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            "*.so",
            ".Python",
            "build/",
            "develop-eggs/",
            "dist/",
            "downloads/",
            "eggs/",
            ".eggs/",
            "lib/",
            "lib64/",
            "parts/",
            "sdist/",
            "var/",
            "wheels/",
            "pip-wheel-metadata/",
            "share/python-wheels/",
            "*.egg-info/",
            ".installed.cfg",
            "*.egg",
            "MANIFEST",
            ".env",
            ".venv/",
            "venv/",
            "env/",
            "ENV/",
            ".tox/",
            ".nox/",
            ".coverage",
            ".coverage.*",
            ".cache",
            "nosetests.xml",
            "coverage.xml",
            "*.cover",
            "*.py,cover",
            ".hypothesis/",
            ".pytest_cache/",
            "cover/",
            "htmlcov/",
            ".mypy_cache/",
        ],
        "java": [
            "target/",
            "*.class",
            "*.jar",
            "*.war",
            "*.ear",
            "hs_err_pid*",
            ".gradle/",
            "gradle-app.setting",
            "!gradle-wrapper.jar",
            ".idea/",
            "*.iws",
            "*.iml",
            "*.ipr",
            ".classpath",
            ".project",
            ".settings/",
            "bin/",
        ],
        "dotnet": [
            "bin/",
            "obj/",
            "*.user",
            "*.suo",
            "*.cache",
            "packages/",
            ".vs/",
            "*.tmp",
            "TestResults/",
            "*.log",
        ],
        "go": [
            "vendor/",
            "*.test",
            "*.out",
        ],
        "rust": [
            "target/",
            "Cargo.lock",
            "**/*.rs.bk",
        ],
        "cpp": [
            "build/",
            "cmake-build-*/",
            "*.o",
            "*.obj",
            "*.exe",
            "*.dll",
            "*.so",
            "*.dylib",
            "*.a",
            "*.lib",
            "*.pdb",
            "*.ilk",
            "*.exp",
            "*.exe.manifest",
        ],
        "php": [
            "vendor/",
            "composer.lock",
            "*.log",
        ],
        "ruby": [
            ".bundle/",
            ".sass-cache/",
            ".gem",
            "Gemfile.lock",
            "vendor/",
        ],
        "swift": [
            ".build/",
            "*.xcodeproj/xcuserdata/",
            "*.xcodeproj/project.xcworkspace/xcuserdata/",
            "*.xcworkspace/xcuserdata/",
            "DerivedData/",
        ],
        "unknown": [
            # Universal ignores for unknown project types
            ".git/",
            ".svn/",
            ".hg/",
            ".DS_Store",
            "Thumbs.db",
            "*.log",
            "*.tmp",
            "*.temp",
            ".env*",
            "coverage/",
            "dist/",
            "build/",
            ".cache/",
            "node_modules/",
            "__pycache__/",
            "*.pyc",
            "target/",
            "bin/",
            "obj/",
            ".vs/",
            ".idea/",
        ],
    }

    def __init__(self) -> None:
        """Initialize the IgnoreManager."""
        self._project_detector = ProjectDetector()
        self._gitignore_parser = GitignoreParser()

    def get_ignore_function(self, project_path: Path) -> Callable[[str, bool], bool]:
        """
        Get the appropriate ignore function for a project.

        Priority:
        1. If .gitignore exists, use its patterns
        2. Otherwise, use default patterns based on detected project type

        Args:
            project_path: Path to the project root

        Returns:
            Ignore function compatible with shutil.copytree
        """
        gitignore_path = project_path / ".gitignore"

        if gitignore_path.exists():
            # Use .gitignore patterns
            patterns = self._gitignore_parser.parse_gitignore(gitignore_path)
            return self._gitignore_parser.create_ignore_function(patterns)
        else:
            # Use default patterns based on project type
            project_type = self._project_detector.detect_project_type(project_path)
            default_patterns = self.DEFAULT_IGNORES.get(
                project_type, self.DEFAULT_IGNORES["unknown"]
            )
            return self._gitignore_parser.create_ignore_function(default_patterns)
