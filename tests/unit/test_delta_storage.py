import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server.models.state_model import State
from src.mcp_server.services.git_manager import GitManager
from src.mcp_server.services.state_service import StateService


class TestDeltaStorage:
    """Test delta storage optimization for file hashes."""

    def test_compute_changes_since_last_state_deltas(self):
        """Test that compute_changes_since_last_state returns deltas correctly."""
        git_manager = GitManager()

        # Create temporary directory with last state files to get actual hashes
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files as they were in last state
            (temp_path / "file1.py").write_text("content1")
            (temp_path / "file2.py").write_text("content2")
            (temp_path / "deleted.py").write_text("content3")

            # Get actual hashes for last state
            last_hashes = git_manager.get_directory_hashes(temp_path)

            # Now modify files for current state
            (temp_path / "file2.py").write_text("content2 changed")  # changed
            (temp_path / "file3.py").write_text("content3")  # new
            (temp_path / "deleted.py").unlink()  # deleted

            diff_info, delta_hashes = git_manager.compute_changes_since_last_state(
                project_path=temp_path, last_state_file_hashes=last_hashes, is_genesis=False
            )

            # Check deltas: only changed/new/deleted files
            assert "file1.py" not in delta_hashes  # unchanged
            assert delta_hashes.get("file2.py") is not None  # changed
            assert delta_hashes.get("file3.py") is not None  # new
            assert delta_hashes.get("deleted.py") is None  # deleted

    def test_compute_changes_since_last_state_genesis(self):
        """Test that genesis returns full hashes."""
        git_manager = GitManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.py").write_text("content1")

            diff_info, delta_hashes = git_manager.compute_changes_since_last_state(
                project_path=temp_path,
                last_state_file_hashes={},  # empty for genesis
                is_genesis=True,
            )

            # Should return full current hashes
            assert "file1.py" in delta_hashes
            assert isinstance(delta_hashes["file1.py"], str)

    def test_reconstruct_file_hashes(self):
        """Test reconstruction of full hashes from deltas."""
        # Mock state repo
        mock_state_repo = MagicMock()

        # Mock genesis state with full hashes
        genesis_state = State(
            state_number=0,
            user_prompt="genesis",
            branch_name="main",
            git_diff_info="",
            hash="genesis_hash",
            file_hashes={"file1.py": "hash1", "file2.py": "hash2"},
        )

        # Mock state 1 with deltas: file2 changed, file3 added
        state1 = State(
            state_number=1,
            user_prompt="change",
            branch_name="main",
            git_diff_info="",
            hash="state1_hash",
            file_hash_deltas={"file2.py": "hash2_new", "file3.py": "hash3"},
        )

        mock_state_repo.get_by_number.side_effect = lambda n: {0: genesis_state, 1: state1}.get(n)

        # Create state service with mock repo
        state_service = StateService(
            state_repo=mock_state_repo,
            transition_repo=MagicMock(),
            git_manager=GitManager(),
            settings=MagicMock(),
        )

        # Reconstruct hashes for state 1
        reconstructed = state_service._reconstruct_file_hashes(
            1, {"file2.py": "hash2_new", "file3.py": "hash3"}
        )

        expected = {
            "file1.py": "hash1",  # from genesis
            "file2.py": "hash2_new",  # updated in state 1
            "file3.py": "hash3",  # added in state 1
        }
        assert reconstructed == expected

    def test_new_transition_uses_current_state_as_delta_baseline(self):
        """Transition deltas must be computed against the current state, not the previous one."""
        mock_state_repo = MagicMock()
        mock_transition_repo = MagicMock()
        mock_git_manager = MagicMock()
        mock_settings = MagicMock()
        mock_settings.docker_volume_name = "/tmp/volume"
        mock_settings.sqlite_path = "/tmp/test.db"

        current_state = State(
            state_number=2,
            user_prompt="Current",
            branch_name="main",
            git_diff_info="",
            hash="current_hash",
            file_hash_deltas={"file.txt": "current-hash"},
        )
        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="",
            hash="genesis_hash",
            file_hashes={"file.txt": "genesis-hash"},
        )
        state1 = State(
            state_number=1,
            user_prompt="State 1",
            branch_name="main",
            git_diff_info="",
            hash="state1_hash",
            file_hash_deltas={"file.txt": "state1-hash"},
        )

        mock_state_repo.get_current.return_value = current_state
        mock_state_repo.get_by_number.side_effect = lambda n: {0: genesis_state, 1: state1, 2: current_state}.get(n)
        mock_state_repo.create_next.side_effect = lambda state: setattr(state, "state_number", 3) or True
        mock_state_repo.set_current.return_value = True
        mock_transition_repo.create_next.return_value = True
        mock_git_manager.compute_changes_since_last_state.return_value = ("{}", {"file.txt": "new-hash"})

        service = StateService(
            state_repo=mock_state_repo,
            transition_repo=mock_transition_repo,
            git_manager=mock_git_manager,
            settings=mock_settings,
        )
        service._project_path = Path("/tmp/project")
        service.branch_detector = MagicMock()
        service.branch_detector.get_current_branch_name.return_value = "main"

        with patch("src.mcp_server.services.state_service.is_initialized", return_value=True):
            success, _, _ = service.new_state_transition("Recovery prompt")

        assert success is True
        assert mock_git_manager.compute_changes_since_last_state.call_args.kwargs["last_state_file_hashes"] == {
            "file.txt": "current-hash"
        }

    def test_state_model_with_deltas(self):
        """Test State model handles deltas correctly."""
        state = State(
            state_number=1,
            user_prompt="test",
            branch_name="main",
            git_diff_info="",
            hash="test_hash",
            file_hashes={"file1.py": "hash1"},
            file_hash_deltas={"file1.py": "hash1", "file2.py": "hash2"},
        )

        assert state.file_hashes == {"file1.py": "hash1"}
        assert state.file_hash_deltas == {"file1.py": "hash1", "file2.py": "hash2"}

        # Test serialization
        data = state.to_dict()
        assert "file_hash_deltas" in data

        # Test deserialization
        restored = State.from_dict(data)
        assert restored.file_hash_deltas == state.file_hash_deltas
