import tempfile
from pathlib import Path

from src.mcp_server.services.git_manager import GitManager
from src.mcp_server.utils.ignore_manager import IgnoreManager


def test_get_directory_hashes_excludes_binaries():
    """Test that binary files are excluded from hashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        # Text file
        (dir_path / "script.py").write_text('print("hello")')
        # Binary file
        (dir_path / "data.db").write_bytes(b"binary data")
        (dir_path / "image.png").write_bytes(b"image data")

        manager = GitManager()
        hashes = manager.get_directory_hashes(dir_path)

        assert "script.py" in hashes
        assert "data.db" not in hashes
        assert "image.png" not in hashes


def test_get_working_diff():
    """Test getting working directory diff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Initialize git repo
        manager = GitManager(repo_path)
        manager.init_repo(repo_path)

        # Create and commit a file
        test_file = repo_path / "test.txt"
        test_file.write_text("initial content")
        manager._run_git_command(["git", "add", "test.txt"], cwd=repo_path)
        manager._run_git_command(["git", "commit", "-m", "initial commit"], cwd=repo_path)

        # Modify the file
        test_file.write_text("modified content")

        # Get working diff
        diff = manager.get_working_diff(repo_path)
        assert "modified content" in diff
        assert "-initial content" in diff


def test_binary_content_detection():
    """Test binary detection via null bytes, non-ASCII ratio, and size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        manager = GitManager()

        # Create a text file (should not be binary)
        text_file = dir_path / "text.txt"
        text_file.write_text("plain text")
        assert manager._is_binary_file(text_file) is False

        # Create file with null bytes (should be binary)
        null_file = dir_path / "null.bin"
        null_file.write_bytes(b"text\x00\x00null")
        assert manager._is_binary_file(null_file) is True

        # Create file with high non-ASCII ratio (>30%) (should be binary)
        nonascii = dir_path / "nonascii.bin"
        nonascii.write_bytes(bytes(range(128, 255)) * 10)
        assert manager._is_binary_file(nonascii) is True

        # Create large file (>1MB) (should be binary due to size limit)
        large = dir_path / "large.txt"
        with open(large, "wb") as f:
            f.write(b"x" * (2 * 1024 * 1024))  # 2MB
        assert manager._is_binary_file(large) is True

        # Clean up large file to avoid disk space issues
        large.unlink()


def test_sync_project_to_volume_replaces_target_and_matches_hashes():
    """Test sync_project_to_volume fully refreshes the target copy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()

        (source / "tracked.txt").write_text("new content")
        (source / "nested").mkdir()
        (source / "nested" / "child.txt").write_text("child content")

        (target / "tracked.txt").write_text("old content")
        (target / "stale.txt").write_text("remove me")

        manager = GitManager()

        assert manager.sync_project_to_volume(source, target) is True
        assert (target / "tracked.txt").read_text() == "new content"
        assert not (target / "stale.txt").exists()
        assert manager.get_directory_hashes(source) == manager.get_directory_hashes(target)


def test_sync_project_to_volume_respects_nested_gitignore_component_patterns():
    """Test sync_project_to_volume excludes nested node_modules/.next from plain .gitignore names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()

        (source / ".gitignore").write_text("node_modules\n.next\n")
        (source / "frontend" / "node_modules" / "react").mkdir(parents=True)
        (source / "frontend" / "node_modules" / "react" / "package.json").write_text("{}")
        (source / "frontend" / ".next" / "cache").mkdir(parents=True)
        (source / "frontend" / ".next" / "cache" / "build.txt").write_text("cache")
        (source / "frontend" / "src").mkdir(parents=True)
        (source / "frontend" / "src" / "app.ts").write_text("export const ok = true;\n")

        manager = GitManager()
        ignore_manager = IgnoreManager()

        assert manager.sync_project_to_volume(source, target, ignore_manager=ignore_manager) is True
        assert not (target / "frontend" / "node_modules").exists()
        assert not (target / "frontend" / ".next").exists()
        assert (target / "frontend" / "src" / "app.ts").exists()
