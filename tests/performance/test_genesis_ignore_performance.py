"""Performance tests for genesis_tool ignore functionality."""

import os
import tempfile
import time
from pathlib import Path

import pytest

from src.mcp_server.services.state_service import StateService
from src.mcp_server.utils.ignore_manager import IgnoreManager


class TestGenesisIgnorePerformance:
    """Performance tests for genesis tool with ignore functionality."""

    def test_ignore_function_performance(self):
        """Test that ignore functions perform well with many files."""
        ignore_manager = IgnoreManager()

        # Create a mock project path
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)

            # Create package.json to simulate Node.js project
            (project_path / "package.json").write_text('{"name": "test"}')

            # Get ignore function
            ignore_func = ignore_manager.get_ignore_function(project_path)

            # Test many paths quickly
            test_paths = [
                "node_modules/express/index.js",
                "node_modules/lodash/dist/lodash.js",
                "src/index.js",
                "README.md",
                ".git/config",
                "__pycache__/module.pyc",
                "build/artifact.js",
                "normal_file.txt",
                "dist/bundle.js",
                "coverage/lcov-report/index.html",
                ".vscode/settings.json",
                ".idea/workspace.xml",
                "debug.log",
                "npm-debug.log",
                "*.log",
                "vendor/bundle/ruby/2.7.0/gems/activerecord-6.1.4/lib/active_record.rb",
            ]

            start_time = time.time()
            results = []
            for path in test_paths * 100:  # Test 1500 path evaluations
                # Determine if it's a directory (simple heuristic)
                is_dir = not "." in Path(path).name or path.endswith("/")
                results.append(ignore_func(path, is_dir))

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time (less than 0.5 seconds for 1500 evaluations)
            assert duration < 0.5, f"Ignore function too slow: {duration:.3f}s for 1500 evaluations"

            # Verify some expected results
            assert results[0] is True  # node_modules should be ignored
            assert results[2] is False  # src should not be ignored
            assert results[6] is True  # .git should be ignored

    def test_large_directory_structure_ignore(self):
        """Test ignore functionality with a moderately large directory structure."""
        ignore_manager = IgnoreManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)

            # Create package.json
            (project_path / "package.json").write_text('{"name": "test"}')

            # Create a moderately large directory structure
            node_modules = project_path / "node_modules"
            node_modules.mkdir()

            # Create 50 mock packages
            for i in range(50):
                pkg_dir = node_modules / f"package_{i}"
                pkg_dir.mkdir()
                (pkg_dir / "package.json").write_text(f'{{"name": "package_{i}"}}')
                (pkg_dir / "index.js").write_text(f'console.log("package_{i}");')

                # Add some nested files
                lib_dir = pkg_dir / "lib"
                lib_dir.mkdir()
                (lib_dir / "main.js").write_text("main code")

            # Create some files that should NOT be ignored
            src_dir = project_path / "src"
            src_dir.mkdir()
            (src_dir / "index.js").write_text('console.log("main app");')

            (project_path / "README.md").write_text("# Test")

            # Get ignore function and test
            ignore_func = ignore_manager.get_ignore_function(project_path)

            # Test some files
            assert ignore_func("node_modules", True) is True
            assert ignore_func("node_modules/package_1", True) is True
            assert ignore_func("node_modules/package_1/index.js", False) is True
            assert ignore_func("src", True) is False
            assert ignore_func("src/index.js", False) is False
            assert ignore_func("README.md", False) is False

            # Count ignored vs not ignored in a walk
            ignored_count = 0
            not_ignored_count = 0

            for root, dirs, files in os.walk(project_path):
                root_path = Path(root)
                rel_root = root_path.relative_to(project_path)

                # Check directories (but don't modify dirs for this test - we want to count all)
                for d in dirs:
                    rel_path = rel_root / d if rel_root != Path(".") else Path(d)
                    if ignore_func(str(rel_path), True):
                        ignored_count += 1
                    else:
                        not_ignored_count += 1

                # Check files
                for f in files:
                    rel_path = rel_root / f if rel_root != Path(".") else Path(f)
                    if ignore_func(str(rel_path), False):
                        ignored_count += 1
                    else:
                        not_ignored_count += 1

            # Should have ignored most files in node_modules but kept source files
            # With 50 packages × (1 package.json + 1 index.js + 1 lib/main.js) = 150 ignored files
            # Plus the node_modules directory itself
            assert ignored_count > 100, f"Should ignore many node_modules files: {ignored_count}"
            assert (
                not_ignored_count >= 3
            ), f"Should keep at least README and src files: {not_ignored_count}"
