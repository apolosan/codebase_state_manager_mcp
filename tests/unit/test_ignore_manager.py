"""Tests for ignore_manager module."""

import tempfile
from pathlib import Path

import pytest

from src.mcp_server.utils.ignore_manager import (
    GitignoreParser,
    IgnoreManager,
    ProjectDetector,
)


class TestProjectDetector:
    """Test ProjectDetector functionality."""

    def test_detect_nodejs_project(self):
        """Test detection of Node.js projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "package.json").write_text('{"name": "test"}')

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "nodejs"

    def test_detect_python_project(self):
        """Test detection of Python projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "pyproject.toml").write_text('[tool.poetry]\nname = "test"')

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "python"

    def test_detect_python_poetry_lock(self):
        """Test detection of Python projects via poetry.lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "poetry.lock").write_text("# Poetry lock file")

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "python"

    def test_detect_rust_project(self):
        """Test detection of Rust projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "Cargo.toml").write_text('[package]\nname = "test"')

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "rust"

    def test_detect_java_project(self):
        """Test detection of Java projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "pom.xml").write_text('<project><modelVersion>4.0.0</modelVersion></project>')

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "java"

    def test_detect_dotnet_project(self):
        """Test detection of .NET projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "test.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>')

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "dotnet"

    def test_detect_unknown_project(self):
        """Test detection returns 'unknown' for unrecognized projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "random.txt").write_text("some content")

            detector = ProjectDetector()
            result = detector.detect_project_type(project_path)
            assert result == "unknown"

    def test_detect_nonexistent_path(self):
        """Test detection with nonexistent path."""
        detector = ProjectDetector()
        result = detector.detect_project_type(Path("/nonexistent/path"))
        assert result == "unknown"


class TestGitignoreParser:
    """Test GitignoreParser functionality."""

    def test_parse_gitignore_basic_patterns(self):
        """Test parsing basic gitignore patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            gitignore_path = Path(temp_dir) / ".gitignore"
            gitignore_path.write_text("*.log\nnode_modules/\n__pycache__/\n")

            parser = GitignoreParser()
            patterns = parser.parse_gitignore(gitignore_path)

            assert "*.log" in patterns
            assert "node_modules/" in patterns
            assert "__pycache__/" in patterns

    def test_parse_gitignore_with_comments(self):
        """Test parsing gitignore with comments and empty lines."""
        with tempfile.TemporaryDirectory() as temp_dir:
            gitignore_path = Path(temp_dir) / ".gitignore"
            gitignore_path.write_text("# Comment\n\n*.log\n# Another comment\nnode_modules/\n")

            parser = GitignoreParser()
            patterns = parser.parse_gitignore(gitignore_path)

            assert "*.log" in patterns
            assert "node_modules/" in patterns
            assert len(patterns) == 2

    def test_parse_nonexistent_gitignore(self):
        """Test parsing nonexistent gitignore returns empty list."""
        parser = GitignoreParser()
        patterns = parser.parse_gitignore(Path("/nonexistent/.gitignore"))
        assert patterns == []

    def test_create_ignore_function_basic_matching(self):
        """Test ignore function with basic patterns."""
        patterns = ["*.log", "node_modules/"]
        parser = GitignoreParser()
        ignore_func = parser.create_ignore_function(patterns)

        # Should ignore log files
        assert ignore_func("debug.log", False) is True
        assert ignore_func("error.log", False) is True

        # Should ignore node_modules directory
        assert ignore_func("node_modules", True) is True
        assert ignore_func("node_modules/express", False) is True

        # Should not ignore other files
        assert ignore_func("main.py", False) is False
        assert ignore_func("src", True) is False

    def test_create_ignore_function_directory_patterns(self):
        """Test ignore function with directory-only patterns."""
        patterns = ["build/"]
        parser = GitignoreParser()
        ignore_func = parser.create_ignore_function(patterns)

        # Should ignore build directory
        assert ignore_func("build", True) is True
        # Should not ignore build file
        assert ignore_func("build", False) is False

    def test_create_ignore_function_always_ignores_git(self):
        """Test that .git is always ignored regardless of patterns."""
        patterns = []  # No patterns
        parser = GitignoreParser()
        ignore_func = parser.create_ignore_function(patterns)

        assert ignore_func(".git", True) is True
        assert ignore_func(".git/config", False) is True
        assert ignore_func("subdir/.git", True) is True

    def test_create_ignore_function_nested_directory_patterns(self):
        """Test ignore function with nested directory patterns."""
        patterns = ["node_modules/", "__pycache__/"]
        parser = GitignoreParser()
        ignore_func = parser.create_ignore_function(patterns)

        # Should ignore nested node_modules
        assert ignore_func("node_modules", True) is True
        assert ignore_func("some/node_modules", True) is True
        assert ignore_func("deep/nested/node_modules", True) is True
        assert ignore_func("some/node_modules/package.json", False) is True

        # Should ignore nested __pycache__
        assert ignore_func("__pycache__", True) is True
        assert ignore_func("src/__pycache__", True) is True
        assert ignore_func("src/__pycache__/module.pyc", False) is True

        # Should not ignore unrelated paths
        assert ignore_func("some", True) is False
        assert ignore_func("src", True) is False

    def test_matches_pattern_wildcards(self):
        """Test pattern matching with wildcards."""
        # Test * wildcard
        assert GitignoreParser._matches_pattern("test.log", "*.log", False) is True
        assert GitignoreParser._matches_pattern("test.txt", "*.log", False) is False

        # Test ? wildcard
        assert GitignoreParser._matches_pattern("test1.log", "test?.log", False) is True
        assert GitignoreParser._matches_pattern("test12.log", "test?.log", False) is False

    def test_matches_pattern_directory_only(self):
        """Test directory-only patterns (ending with /)."""
        # Directory pattern should only match directories
        assert GitignoreParser._matches_pattern("node_modules", "node_modules/", True) is True
        assert GitignoreParser._matches_pattern("node_modules", "node_modules/", False) is False

    def test_matches_pattern_negation_ignored(self):
        """Test that negation patterns are ignored (simplified implementation)."""
        # Our implementation ignores negation patterns for simplicity
        assert GitignoreParser._matches_pattern("important.log", "!important.log", False) is False

    def test_matches_pattern_nested_directories(self):
        """Test that directory patterns match nested occurrences."""
        # Directory patterns should match at any depth
        assert GitignoreParser._matches_pattern("node_modules", "node_modules/", True) is True
        assert GitignoreParser._matches_pattern("node_modules/express", "node_modules/", True) is True
        assert GitignoreParser._matches_pattern("some/node_modules", "node_modules/", True) is True
        assert GitignoreParser._matches_pattern("some/node_modules/package.json", "node_modules/", False) is True
        assert GitignoreParser._matches_pattern("deep/nested/path/node_modules", "node_modules/", True) is True
        assert GitignoreParser._matches_pattern("deep/nested/path/node_modules/lib", "node_modules/", True) is True

        # Should not match unrelated directories
        assert GitignoreParser._matches_pattern("some", "node_modules/", True) is False
        assert GitignoreParser._matches_pattern("some/deep", "node_modules/", True) is False


class TestIgnoreManager:
    """Test IgnoreManager functionality."""

    def test_get_ignore_function_with_gitignore(self):
        """Test ignore function generation when .gitignore exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            gitignore_path = project_path / ".gitignore"
            gitignore_path.write_text("*.log\nnode_modules/\n")

            manager = IgnoreManager()
            ignore_func = manager.get_ignore_function(project_path)

            # Should use gitignore patterns
            assert ignore_func("debug.log", False) is True
            assert ignore_func("node_modules", True) is True
            assert ignore_func("main.py", False) is False

    def test_get_ignore_function_nodejs_fallback(self):
        """Test fallback to Node.js patterns when no .gitignore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "package.json").write_text('{"name": "test"}')

            manager = IgnoreManager()
            ignore_func = manager.get_ignore_function(project_path)

            # Should use Node.js default patterns
            assert ignore_func("node_modules", True) is True
            assert ignore_func("npm-debug.log", False) is True
            assert ignore_func("dist", True) is True

    def test_get_ignore_function_python_fallback(self):
        """Test fallback to Python patterns when no .gitignore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "pyproject.toml").write_text('[tool.poetry]\nname = "test"')

            manager = IgnoreManager()
            ignore_func = manager.get_ignore_function(project_path)

            # Should use Python default patterns
            assert ignore_func("__pycache__", True) is True
            assert ignore_func("*.pyc", False) is True
            assert ignore_func(".venv", True) is True

    def test_get_ignore_function_unknown_fallback(self):
        """Test fallback to universal patterns for unknown project types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / "random.txt").write_text("content")

            manager = IgnoreManager()
            ignore_func = manager.get_ignore_function(project_path)

            # Should use universal default patterns
            assert ignore_func("node_modules", True) is True
            assert ignore_func("__pycache__", True) is True
            assert ignore_func(".DS_Store", False) is True
            assert ignore_func("*.log", False) is True

    def test_get_ignore_function_empty_directory(self):
        """Test behavior with empty directory (no project files)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)

            manager = IgnoreManager()
            ignore_func = manager.get_ignore_function(project_path)

            # Should use universal defaults
            assert ignore_func("node_modules", True) is True