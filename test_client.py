#!/usr/bin/env python3
"""
Test client for MCP server.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

async def test_server():
    """Test MCP server communication."""
    import os
    
    # Start server as subprocess
    cmd = [
        "uv", "run", "--project", str(project_root), 
        "python", "init_neo4j_and_mcp.py"
    ]
    
    # Set environment variables
    env = os.environ.copy()
    env.update({
        "DB_MODE": "sqlite",
        "NEO4J_ENABLED": "false",
        "LOG_LEVEL": "DEBUG"
    })
    
    print(f"Starting server: {' '.join(cmd)}")
    
    # Start server process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1
    )
    
    # Give server time to initialize
    await asyncio.sleep(2)
    
    # Read stderr output
    stderr_lines = []
    while True:
        line = proc.stderr.readline()
        if line:
            stderr_lines.append(line.strip())
            print(f"[SERVER STDERR] {line.strip()}")
        else:
            break
    
    # Try to send initialization message (MCP handshake)
    import json
    init_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            },
            "capabilities": {}
        }
    }
    
    print(f"Sending: {json.dumps(init_message)}")
    proc.stdin.write(json.dumps(init_message) + "\n")
    proc.stdin.flush()
    
    # Try to read response
    await asyncio.sleep(1)
    response = proc.stdout.readline()
    print(f"Received: {response}")
    
    # Cleanup
    proc.terminate()
    proc.wait()
    
    print("Test completed")

if __name__ == "__main__":
    import os
    asyncio.run(test_server())