#!/usr/bin/env python3
"""Deprecated compatibility launcher for the MCP server.

Prefer `run_mcp_server.py`. This alias is kept only to avoid breaking older
agent configurations while the startup flow remains fully compatible.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.mcp_server.__main__ import main


if __name__ == "__main__":
    main()
