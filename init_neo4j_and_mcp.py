#!/usr/bin/env python3
"""
Neo4j Container Manager and MCP Server Launcher
Automatically manages Neo4j container and launches MCP server
"""

import sys
import os
import time
import logging
from pathlib import Path

# Load environment variables from .env file if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=str(env_path), override=False)

# Add src to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    import docker
    from docker.errors import DockerException
    from neo4j import GraphDatabase
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}", file=sys.stderr)
    print("[INFO] Install with: uv add docker neo4j", file=sys.stderr)
    sys.exit(1)

# Configuration
CONTAINER_NAME = "mcp-neo4j-server"
NEO4J_VERSION = "latest"
NEO4J_PASSWORD = "password"
NEO4J_PORT_BOLT = 7687
NEO4J_PORT_HTTP = 7474

logging.basicConfig(
    level=logging.INFO,
    format='[INFO] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_docker():
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        logger.info("Docker is available and running")
        return client
    except DockerException as e:
        logger.error(f"Docker error: {e}")
        sys.exit(1)

def wait_for_neo4j(uri: str, user: str, password: str, max_attempts: int = 30):
    """Wait for Neo4j to be ready."""
    logger.info("Waiting for Neo4j to be ready...")

    for attempt in range(1, max_attempts + 1):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                result = session.run("MATCH () RETURN count(*) LIMIT 1")
                result.single()
            driver.close()
            logger.info("Neo4j is ready!")
            return True
        except Exception as e:
            logger.info(f"Attempt {attempt}/{max_attempts} - Neo4j not ready yet: {e}")
            time.sleep(2)

    logger.error(f"Neo4j did not become ready after {max_attempts} attempts")
    return False

def manage_container(client):
    """Manage Neo4j container: check/create/start as needed."""
    try:
        # Check if container exists
        containers = client.containers.list(all=True, filters={"name": CONTAINER_NAME})

        if containers:
            container = containers[0]
            logger.info(f"Found existing container: {CONTAINER_NAME}")

            # Check if running
            if container.status == "running":
                logger.info("Container is already running")
            else:
                logger.info("Starting existing container...")
                container.start()
                logger.info("Container started")

                # Wait for Neo4j to be ready
                uri = f"bolt://localhost:{NEO4J_PORT_BOLT}"
                if not wait_for_neo4j(uri, "neo4j", NEO4J_PASSWORD):
                    sys.exit(1)

        else:
            logger.info(f"Creating new Neo4j container: {CONTAINER_NAME}")

            # Create and start new container
            container = client.containers.run(
                f"neo4j:{NEO4J_VERSION}",
                name=CONTAINER_NAME,
                ports={
                    f"{NEO4J_PORT_BOLT}/tcp": NEO4J_PORT_BOLT,
                    f"{NEO4J_PORT_HTTP}/tcp": NEO4J_PORT_HTTP
                },
                environment={
                    "NEO4J_AUTH": f"neo4j/{NEO4J_PASSWORD}",
                    "NEO4J_PLUGINS": '["graph-data-science"]'
                },
                volumes={
                    "mcp_neo4j_data": {"bind": "/data", "mode": "rw"},
                    "mcp_neo4j_logs": {"bind": "/logs", "mode": "rw"}
                },
                detach=True
            )

            logger.info("Container created and started")

            # Wait for Neo4j to be ready
            uri = f"bolt://localhost:{NEO4J_PORT_BOLT}"
            if not wait_for_neo4j(uri, "neo4j", NEO4J_PASSWORD):
                sys.exit(1)

    except Exception as e:
        logger.error(f"Error managing container: {e}")
        sys.exit(1)

def main():
    """Main function to manage Neo4j container and launch MCP server."""
    logger.info("Starting MCP Server launcher...")
    
    # Read configuration from environment
    db_mode = os.getenv("DB_MODE", "neo4j").lower()
    neo4j_enabled = os.getenv("NEO4J_ENABLED", "true").lower() in ("true", "1", "yes")
    
    logger.info(f"DB_MODE: {db_mode}, NEO4J_ENABLED: {neo4j_enabled}")
    
    # Only manage Neo4j container if needed
    if db_mode == "neo4j" and neo4j_enabled:
        logger.info("Neo4j is enabled, managing container...")
        # Check Docker availability
        client = check_docker()
        # Manage Neo4j container
        manage_container(client)
        logger.info("Neo4j container is ready.")
    else:
        logger.info("Skipping Neo4j container management (using SQLite or Neo4j disabled)")

    logger.info("Starting MCP Server...")

    # Import and run MCP server
    try:
        logger.info("Importing MCP server module...")
        from mcp_server.mcp_server import main as mcp_main
        logger.info("MCP server module imported successfully")
        logger.info("Calling mcp_main()...")
        mcp_main()
        logger.info("mcp_main() returned (server stopped)")
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()