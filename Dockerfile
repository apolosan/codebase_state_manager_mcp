FROM python:3.10-slim

LABEL maintainer="developer@codebase.local"
LABEL description="Codebase State Manager MCP Server with Neo4j"

# ============================================================================
# Install system dependencies (Git for operations, curl for Neo4j download)
# ============================================================================
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ============================================================================
# Neo4j Installation (Community Edition)
# ============================================================================
ENV NEO4J_VERSION=5.24.0
ENV NEO4J_HOME=/opt/neo4j
ENV NEO4J_DATA=/data/neo4j
ENV NEO4J_LOGS=/data/neo4j/logs

# Create directories for Neo4j
RUN mkdir -p ${NEO4J_DATA} ${NEO4J_LOGS}

# Pre-download Neo4j to speed up first startup (optional optimization)
# Uncomment below to include Neo4j in image (increases size ~200MB)
# RUN curl -L -o /tmp/neo4j.tar.gz \
#     "https://dist.neo4j.org/neo4j-community-${NEO4J_VERSION}-unix.tar.gz" \
#     && tar -xzf /tmp/neo4j.tar.gz -C /opt \
#     && mv /opt/neo4j-community-${NEO4J_VERSION} ${NEO4J_HOME} \
#     && rm /tmp/neo4j.tar.gz

# ============================================================================
# Python Dependencies
# ============================================================================
COPY requirements.txt .
COPY pyproject.toml .

RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Application Code
# ============================================================================
COPY src/ ./src/
COPY scripts/ ./scripts/

# Make entrypoint executable
RUN chmod +x scripts/entrypoint.sh

# ============================================================================
# Environment Variables
# ============================================================================
ENV PYTHONPATH=/app
ENV NEO4J_ENABLED=true
ENV NEO4J_USER=neo4j
ENV NEO4J_PASSWORD=password
ENV NEO4J_URI=bolt://localhost:7687
ENV DB_MODE=neo4j
ENV DOCKER_VOLUME_NAME=codebase_state_volume

# ============================================================================
# Health Check
# ============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('localhost', 7687))
    s.close()
    exit(0)
except:
    exit(1)
" || exit 1

# ============================================================================
# Ports
# ============================================================================
EXPOSE 7474 7687 8080

# ============================================================================
# Entrypoint
# ============================================================================
WORKDIR /app
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Default command (overridden by entrypoint)
CMD ["python", "-m", "src.mcp_server"]
