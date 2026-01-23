#!/usr/bin/env python3
"""
Main entry point for Codebase State Manager MCP Server.

This module initializes and runs the MCP server with all tools configured.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    """Main entry point for the MCP server."""
    from neo4j.exceptions import ServiceUnavailable, SessionExpired

    from src.mcp_server.config import Settings, get_settings
    from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
    from src.mcp_server.repositories.sqlite_repository import create_sqlite_repositories
    from src.mcp_server.services.git_manager import GitManager
    from src.mcp_server.services.state_service import StateService
    from src.mcp_server.tools import mcp_tools
    from src.mcp_server.utils.audit import get_audit_logger
    from src.mcp_server.utils.logging import get_logger, setup_logging
    from src.mcp_server.utils.security import get_rate_limiter

    settings = get_settings()

    setup_logging(log_level=settings.log_level)
    logger = get_logger(__name__)

    logger.info("Starting Codebase State Manager MCP Server...")
    logger.info(f"Database Mode: {settings.db_mode}")
    logger.info(f"Neo4j Connection Timeout: {settings.neo4j_connection_timeout}s")
    logger.info(f"Rate Limiting: {'Enabled' if settings.rate_limit_enabled else 'Disabled'}")
    logger.info(f"Audit Logging: {'Enabled' if settings.audit_enabled else 'Disabled'}")

    rate_limiter = get_rate_limiter()
    if not settings.rate_limit_enabled:
        rate_limiter.disable()
    else:
        rate_limiter.enable()

    audit_logger = get_audit_logger()
    if not settings.audit_enabled:
        audit_logger.disable()
    else:
        audit_logger.enable()

    if settings.db_mode == "neo4j":
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")
        except (ServiceUnavailable, SessionExpired, Exception) as e:
            logger.warning(f"Neo4j connection failed: {e}. Falling back to SQLite.")
            state_repo, transition_repo = create_sqlite_repositories(
                path=settings.sqlite_path,
                settings=settings,
            )
            logger.info(f"Using SQLite at {settings.sqlite_path}")
    else:
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        logger.info(f"Using SQLite at {settings.sqlite_path}")

    git_manager = GitManager()
    state_service = StateService(
        state_repo=state_repo,
        transition_repo=transition_repo,
        git_manager=git_manager,
        settings=settings,
    )

    logger.info("State Service initialized successfully")
    logger.info("Available MCP Tools:")
    for tool_name in dir(mcp_tools):
        if not tool_name.startswith("_"):
            logger.info(f"  - {tool_name}")
    print("\nMCP Server is ready to accept connections.")
    print("Press Ctrl+C to stop.")

    # Start the MCP server
    try:
        logger.info("Importing MCP server app...")
        from .mcp_server import app

        logger.info("MCP server app imported successfully")

        import mcp

        mcp_version = getattr(mcp, "__version__", "unknown")
        logger.info(f"MCP library version: {mcp_version}")

        logger.info("Starting app.run()...")
        # Enable debug logging for MCP
        import logging

        logging.getLogger("mcp").setLevel(logging.DEBUG)
        logging.getLogger("anyio").setLevel(logging.DEBUG)
        logging.getLogger("asyncio").setLevel(logging.DEBUG)

        logger.info("Calling app.run()...")
        app.run()
        logger.info("app.run() returned (server stopped)")
    except Exception as e:
        logger.error(f"MCP Server failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
