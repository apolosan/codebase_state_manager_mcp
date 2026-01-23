"""Integration tests for genesis_tool ignore functionality."""

import tempfile
from pathlib import Path

import pytest

from src.mcp_server.services.state_service import StateService
from src.mcp_server.utils.ignore_manager import IgnoreManager


class TestGenesisIgnoreIntegration:
    """Integration tests for genesis tool with ignore functionality."""

    @pytest.fixture
    def ignore_manager(self):
        """Create IgnoreManager instance."""
        return IgnoreManager()

    def test_genesis_nodejs_project_ignores_correctly(self, ignore_manager, tmp_path):
        """Test that genesis correctly ignores Node.js project artifacts."""
        # Create a mock Node.js project
        project_path = tmp_path / "nodejs_project"
        project_path.mkdir()

        # Create package.json
        (project_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}')

        # Create some files that should be ignored
        node_modules = project_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "express").mkdir()
        (node_modules / "express" / "package.json").write_text('{"name": "express"}')

        (project_path / "npm-debug.log").write_text("debug log")

        # Create files that should NOT be ignored
        (project_path / "src").mkdir()
        (project_path / "src" / "index.js").write_text('console.log("hello");')
        (project_path / "README.md").write_text("# Test project")

        # Test the ignore function
        ignore_func = ignore_manager.get_ignore_function(project_path)

        # Should ignore node_modules and its contents
        assert ignore_func("node_modules", True) is True
        assert ignore_func("node_modules/express", True) is True
        assert ignore_func("node_modules/express/package.json", False) is True

        # Should ignore npm debug logs
        assert ignore_func("npm-debug.log", False) is True

        # Should NOT ignore source files and README
        assert ignore_func("src", True) is False
        assert ignore_func("src/index.js", False) is False
        assert ignore_func("README.md", False) is False

    def test_genesis_python_project_ignores_correctly(self, ignore_manager, tmp_path):
        """Test that genesis correctly ignores Python project artifacts."""
        # Create a mock Python project
        project_path = tmp_path / "python_project"
        project_path.mkdir()

        # Create pyproject.toml
        (project_path / "pyproject.toml").write_text('[tool.poetry]\nname = "test"\nversion = "1.0.0"')

        # Create some files that should be ignored
        pycache = project_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-38.pyc").write_text("compiled python")

        venv = project_path / ".venv"
        venv.mkdir()
        (venv / "bin").mkdir()
        (venv / "bin" / "python").write_text("#!/bin/bash\necho python")

        # Create files that should NOT be ignored
        (project_path / "src").mkdir()
        (project_path / "src" / "main.py").write_text('print("hello")')
        (project_path / "README.md").write_text("# Test project")

        # Test the ignore function
        ignore_func = ignore_manager.get_ignore_function(project_path)

        # Should ignore Python cache
        assert ignore_func("__pycache__", True) is True
        assert ignore_func("__pycache__/module.cpython-38.pyc", False) is True

        # Should ignore virtual environment
        assert ignore_func(".venv", True) is True
        assert ignore_func(".venv/bin/python", True) is True

        # Should NOT ignore source files
        assert ignore_func("src", True) is False
        assert ignore_func("src/main.py", False) is False
        assert ignore_func("README.md", False) is False

    def test_genesis_with_gitignore_uses_gitignore_patterns(self, ignore_manager, tmp_path):
        """Test that genesis uses .gitignore patterns when available."""
        # Create a project with .gitignore
        project_path = tmp_path / "project_with_gitignore"
        project_path.mkdir()

        # Create .gitignore with custom patterns
        (project_path / ".gitignore").write_text("""
# Custom ignore patterns
custom_build/
*.custom
temp/
""")

        # Create files
        (project_path / "custom_build").mkdir()
        (project_path / "custom_build" / "artifact.txt").write_text("content")

        (project_path / "file.custom").write_text("custom file")
        (project_path / "normal_file.txt").write_text("normal")

        (project_path / "temp").mkdir()
        (project_path / "temp" / "tmp.dat").write_text("temp data")

        # Test the ignore function
        ignore_func = ignore_manager.get_ignore_function(project_path)

        # Should ignore based on .gitignore patterns
        assert ignore_func("custom_build", True) is True
        assert ignore_func("custom_build/artifact.txt", False) is True
        assert ignore_func("file.custom", False) is True
        assert ignore_func("temp", True) is True

        # Should NOT ignore normal files
        assert ignore_func("normal_file.txt", False) is False

        # Should still ignore .git
        assert ignore_func(".git", True) is True

    def test_genesis_unknown_project_uses_universal_ignores(self, ignore_manager, tmp_path):
        """Test that unknown projects use universal ignore patterns."""
        # Create a project without recognizable markers
        project_path = tmp_path / "unknown_project"
        project_path.mkdir()

        # Create some common files that should be ignored universally
        (project_path / "node_modules" / "package.json").mkdir(parents=True)
        (project_path / "__pycache__" / "file.pyc").mkdir(parents=True)
        (project_path / ".DS_Store").write_text("mac file")
        (project_path / "debug.log").write_text("log content")

        # Create files that should NOT be ignored
        (project_path / "source.txt").write_text("source")

        # Test the ignore function
        ignore_func = ignore_manager.get_ignore_function(project_path)

        # Should ignore universal patterns
        assert ignore_func("node_modules", True) is True
        assert ignore_func("__pycache__", True) is True
        assert ignore_func(".DS_Store", False) is True
        assert ignore_func("debug.log", False) is True

        # Should NOT ignore source files
        assert ignore_func("source.txt", False) is False

    def test_genesis_empty_directory_uses_universal_ignores(self, ignore_manager, tmp_path):
        """Test that empty directories use universal ignore patterns."""
        # Create an empty project directory
        project_path = tmp_path / "empty_project"
        project_path.mkdir()

        # Test the ignore function
        ignore_func = ignore_manager.get_ignore_function(project_path)

        # Should still ignore universal patterns even for empty projects
        assert ignore_func("node_modules", True) is True
        assert ignore_func("__pycache__", True) is True
        assert ignore_func(".git", True) is True
        assert ignore_func("*.log", False) is True

        # Should NOT ignore regular files
        assert ignore_func("main.py", False) is False