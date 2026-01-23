#!/usr/bin/env python3
"""
Test script to verify MCP server initialization.
"""
import os
import sys
from pathlib import Path

# Set environment variables for SQLite mode
os.environ["DB_MODE"] = "sqlite"
os.environ["NEO4J_ENABLED"] = "false"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["AUDIT_ENABLED"] = "false"
os.environ["VOLUME_PATH"] = "/tmp/codebase"

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

print("Testing MCP server imports...")

try:
    # Test basic imports
    from mcp_server.config import Settings, get_settings
    print("✓ config imported")
    
    from mcp_server.repositories.sqlite_repository import create_sqlite_repositories
    print("✓ sqlite_repository imported")
    
    from mcp_server.services.git_manager import GitManager
    print("✓ git_manager imported")
    
    from mcp_server.services.state_service import StateService
    print("✓ state_service imported")
    
    from mcp_server.tools import mcp_tools
    print("✓ mcp_tools imported")
    
    # Test settings
    settings = get_settings()
    print(f"✓ Settings loaded: db_mode={settings.db_mode}")
    
    # Test repository creation
    state_repo, transition_repo = create_sqlite_repositories(
        path=settings.sqlite_path,
        settings=settings,
    )
    print("✓ SQLite repositories created")
    
    # Test service initialization
    git_manager = GitManager()
    state_service = StateService(
        state_repo=state_repo,
        transition_repo=transition_repo,
        git_manager=git_manager,
        settings=settings,
    )
    print("✓ StateService initialized")
    
    # Test MCP server import
    from mcp_server.mcp_server import app
    print("✓ MCP server app imported")
    
    print("\n✅ All imports and initializations successful!")
    print("MCP server is ready to be used by an MCP client.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)