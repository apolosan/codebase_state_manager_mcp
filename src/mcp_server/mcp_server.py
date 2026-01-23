#!/usr/bin/env python3
"""
MCP Server for Codebase State Manager
Integrates the codebase-state-manager-mcp library with MCP protocol
"""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from mcp.server.fastmcp import FastMCP

from .config import get_settings, reset_settings
from .repositories.sqlite_repository import create_sqlite_repositories
from .repositories.neo4j_repository import create_neo4j_repositories
from .services.git_manager import GitManager
from .services.state_service import StateService
from .tools import (
    genesis, new_state_transition, arbitrary_state_transition,
    get_current_state_number, get_current_state_info, get_state_info,
    total_states, search_states, get_state_transitions, get_transition_info,
    track_transitions
)

settings = get_settings()

if settings.db_mode == "neo4j":
    try:
        state_repo, transition_repo = create_neo4j_repositories(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            settings=settings,
        )
        print(f"[INFO] Using Neo4j: {settings.neo4j_uri}")
    except Exception as e:
        print(f"[WARNING] Neo4j unavailable: {e}, falling back to SQLite")
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        print(f"[INFO] Using SQLite: {settings.sqlite_path}")
else:
    state_repo, transition_repo = create_sqlite_repositories(
        path=settings.sqlite_path,
        settings=settings,
    )
    print(f"[INFO] Using SQLite: {settings.sqlite_path}")

git_manager = GitManager()
state_service = StateService(
    state_repo=state_repo,
    transition_repo=transition_repo,
    git_manager=git_manager,
    settings=settings,
)

app = FastMCP("codebase-state-manager")

@app.tool()
async def genesis_tool() -> dict:
    """Initialize the state machine for a project.

    Creates state #0 and sets up the codebase state machine.
    Automatically detects project path and uses default volume.
    """
    import os
    from pathlib import Path

    # Auto-detect project path (current working directory)
    project_path = str(Path.cwd())

    # Use environment variable or default volume path
    volume_path = os.getenv("VOLUME_PATH", "/tmp/codebase")

    result = genesis(
        state_service=state_service,
        project_path=project_path,
        volume_path=volume_path,
    )
    return result

@app.tool()
async def get_current_state_number_tool() -> dict:
    """Get the current state number."""
    result = get_current_state_number(state_service=state_service)
    return result

@app.tool()
async def total_states_tool() -> dict:
    """Get the total number of states."""
    result = total_states(state_service=state_service)
    return result

@app.tool()
async def new_state_transition_tool(user_prompt: str) -> dict:
    """Create a new state transition from the current state."""
    result = new_state_transition(
        state_service=state_service,
        user_prompt=user_prompt,
    )
    return result

@app.tool()
async def get_current_state_info_tool() -> dict:
    """Get full context of the current state."""
    result = get_current_state_info(state_service=state_service)
    return result

@app.tool()
async def search_states_tool(text: str) -> dict:
    """Search states by prompt content."""
    result = search_states(
        state_service=state_service,
        text=text,
    )
    return result

# Debug: print registered tools
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"MCP Server initialized with app methods: {[name for name in dir(app) if not name.startswith('_')]}")

# List the tool functions we've registered
registered_tool_names = [
    'genesis_tool',
    'get_current_state_number_tool', 
    'total_states_tool',
    'new_state_transition_tool',
    'get_current_state_info_tool',
    'search_states_tool',
]
logger.info(f"Manually registered tool functions: {registered_tool_names}")

def main():
    import logging
    import traceback
    import sys
    
    # Enable debug logging for MCP and anyio
    logging.basicConfig(
        level=logging.DEBUG,
        format='[MCP] %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stderr
    )
    
    # Set specific loggers to DEBUG
    logging.getLogger('mcp').setLevel(logging.DEBUG)
    logging.getLogger('anyio').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    logger.info("Starting MCP server with FastMCP...")
    logger.info(f"Database mode: {settings.db_mode}")
    
    try:
        logger.info("Calling app.run()...")
        app.run()
        logger.info("app.run() returned (server stopped normally)")
    except Exception as e:
        logger.error(f"app.run() failed with exception: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()