#!/usr/bin/env python3
"""
Migration script to convert existing states with full file_hashes to delta storage.

This script should be run after deploying the delta storage changes to convert
existing states to use deltas for better storage efficiency.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server.config import Settings
from mcp_server.repositories.sqlite_repository import create_sqlite_repositories
from mcp_server.services.state_service import StateService, GitManager

def migrate_to_deltas():
    """Migrate existing states to delta storage."""
    settings = Settings()
    settings.docker_volume_name = "mcp_data"  # Adjust as needed

    # Initialize repositories
    state_repo, transition_repo = create_sqlite_repositories(
        str(Path(settings.docker_volume_name) / "states.db"), settings
    )

    git_manager = GitManager()
    state_service = StateService(state_repo, transition_repo, git_manager, settings)

    # Get all states
    states = state_repo.get_all()

    for state in states:
        if state.state_number == 0:
            # Genesis already has full hashes as deltas
            continue

        if hasattr(state, 'file_hash_deltas') and state.file_hash_deltas:
            # Already migrated
            continue

        print(f"Migrating state {state.state_number}")

        # Reconstruct full hashes for this state
        try:
            full_hashes = state_service._reconstruct_file_hashes(
                state.state_number, {}  # Empty deltas to get full reconstruction
            )

            # Compute deltas from previous state
            prev_state = state_repo.get_by_number(state.state_number - 1)
            if prev_state and prev_state.file_hashes:
                # Calculate deltas
                deltas = {}
                for file_path, current_hash in full_hashes.items():
                    if file_path not in prev_state.file_hashes:
                        deltas[file_path] = current_hash  # new file
                    elif prev_state.file_hashes[file_path] != current_hash:
                        deltas[file_path] = current_hash  # changed

                for file_path in prev_state.file_hashes:
                    if file_path not in full_hashes:
                        deltas[file_path] = None  # deleted

                # Update state with deltas
                state.file_hash_deltas = deltas
                state_repo.create(state)  # This will update existing state
                print(f"  Migrated {len(deltas)} delta entries")

        except Exception as e:
            print(f"  Failed to migrate state {state.state_number}: {e}")

    print("Migration complete")

if __name__ == "__main__":
    migrate_to_deltas()