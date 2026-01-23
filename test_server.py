#!/usr/bin/env python3
"""
Test script for Codebase State Manager MCP Server
"""

import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from mcp_server.config import get_settings, reset_settings
from mcp_server.repositories.sqlite_repository import create_sqlite_repositories
from mcp_server.services.git_manager import GitManager
from mcp_server.services.state_service import StateService
from mcp_server.tools import genesis, get_current_state_number, total_states

def main():
    print("Testing Codebase State Manager MCP Server...")

    # Reset settings to reload from env
    reset_settings()

    # Get settings
    settings = get_settings()
    print(f"Database mode: {settings.db_mode}")
    print(f"NEO4J_ENABLED env: {os.getenv('NEO4J_ENABLED')}")
    print(f"DB_MODE env: {os.getenv('DB_MODE')}")

    # Create repositories
    state_repo, transition_repo = create_sqlite_repositories(
        path=settings.sqlite_path,
        settings=settings,
    )

    # Create services
    git_manager = GitManager()
    state_service = StateService(
        state_repo=state_repo,
        transition_repo=transition_repo,
        git_manager=git_manager,
        settings=settings,
    )

    print("Services initialized successfully!")

    # Test basic functions
    try:
        # Test genesis
        print("\nTesting genesis...")
        result = genesis(
            state_service=state_service,
            project_path=str(project_root),
            volume_path="/tmp/test_volume",
        )
        print(f"Genesis result: {result}")

        # Test current state
        print("\nTesting get_current_state_number...")
        result = get_current_state_number(state_service=state_service)
        print(f"Current state: {result}")

        # Test total states
        print("\nTesting total_states...")
        result = total_states(state_service=state_service)
        print(f"Total states: {result}")

        print("\nAll tests passed!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()