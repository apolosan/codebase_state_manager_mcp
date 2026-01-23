#!/usr/bin/env python3
"""
Launcher script for MCP Server
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# Import and run the MCP server
from mcp_server.mcp_server import main

