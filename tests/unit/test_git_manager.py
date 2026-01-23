import tempfile
from pathlib import Path

from src.mcp_server.services.git_manager import GitManager


def test_get_directory_hashes_excludes_binaries():
    """Test that binary files are excluded from hashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        # Text file
        (dir_path / 'script.py').write_text('print("hello")')
        # Binary file
        (dir_path / 'data.db').write_bytes(b'binary data')
        (dir_path / 'image.png').write_bytes(b'image data')

        manager = GitManager()
        hashes = manager.get_directory_hashes(dir_path)

        assert 'script.py' in hashes
        assert 'data.db' not in hashes
        assert 'image.png' not in hashes


def test_get_working_diff():
    """Test getting working directory diff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Initialize git repo
        manager = GitManager(repo_path)
        manager.init_repo(repo_path)

        # Create and commit a file
        test_file = repo_path / 'test.txt'
        test_file.write_text('initial content')
        manager._run_git_command(['git', 'add', 'test.txt'], cwd=repo_path)
        manager._run_git_command(['git', 'commit', '-m', 'initial commit'], cwd=repo_path)

        # Modify the file
        test_file.write_text('modified content')

        # Get working diff
        diff = manager.get_working_diff(repo_path)
        assert 'modified content' in diff
        assert '-initial content' in diff


def test_binary_content_detection():
    """Test binary detection via null bytes, non-ASCII ratio, and size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        manager = GitManager()

        # Create a text file (should not be binary)
        text_file = dir_path / 'text.txt'
        text_file.write_text('plain text')
        assert manager._is_binary_file(text_file) is False

        # Create file with null bytes (should be binary)
        null_file = dir_path / 'null.bin'
        null_file.write_bytes(b'text\x00\x00null')
        assert manager._is_binary_file(null_file) is True

        # Create file with high non-ASCII ratio (>30%) (should be binary)
        nonascii = dir_path / 'nonascii.bin'
        nonascii.write_bytes(bytes(range(128, 255)) * 10)
        assert manager._is_binary_file(nonascii) is True

        # Create large file (>1MB) (should be binary due to size limit)
        large = dir_path / 'large.txt'
        with open(large, 'wb') as f:
            f.write(b'x' * (2 * 1024 * 1024))  # 2MB
        assert manager._is_binary_file(large) is True

        # Clean up large file to avoid disk space issues
        large.unlink()