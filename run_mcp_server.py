#!/usr/bin/env python3
"""Canonical launcher for the Codebase State Manager MCP server."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.mcp_server.__main__ import main


if __name__ == "__main__":
    main()

