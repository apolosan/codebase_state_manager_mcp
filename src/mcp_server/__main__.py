#!/usr/bin/env python3
"""
Main entry point for Codebase State Manager MCP Server.

This module initializes and runs the MCP server with all tools configured.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    """Main entry point for the MCP server."""
    from src.mcp_server.config import Settings, get_settings
    from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
    from src.mcp_server.repositories.sqlite_repository import create_sqlite_repositories
    from src.mcp_server.services.git_manager import GitManager
    from src.mcp_server.services.state_service import StateService
    from src.mcp_server.tools import mcp_tools

    settings = get_settings()
    print(f"Starting Codebase State Manager MCP Server...")
    print(f"Database Mode: {settings.db_mode}")

    if settings.db_mode == "neo4j":
        state_repo, transition_repo = create_neo4j_repositories(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            settings=settings,
        )
        print(f"Connected to Neo4j at {settings.neo4j_uri}")
    else:
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        print(f"Using SQLite at {settings.sqlite_path}")

    git_manager = GitManager()
    state_service = StateService(
        state_repo=state_repo,
        transition_repo=transition_repo,
        git_manager=git_manager,
        settings=settings,
    )

    print("State Service initialized successfully")
    print("Available MCP Tools:")
    for tool_name in dir(mcp_tools):
        if not tool_name.startswith("_"):
            print(f"  - {tool_name}")
    print("\nMCP Server is ready to accept connections.")
    print("Press Ctrl+C to stop.")


if __name__ == "__main__":
    main()
