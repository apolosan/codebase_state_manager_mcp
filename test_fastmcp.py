#!/usr/bin/env python3
"""
Test script to check if FastMCP works independently.
"""
import asyncio
import logging
import sys
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastMCP("test-server")

@app.tool()
async def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

def main():
    print("Starting FastMCP test server...")
    print(f"Python: {sys.version}")
    print(f"MCP version: unknown")
    
    try:
        print("Calling app.run()...")
        app.run()
        print("app.run() returned (server stopped)")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()