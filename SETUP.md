# Setup Guide

This document describes the **current** installation and configuration paths for version **0.2.1** of the project.

It replaces older exploratory setup notes and reflects the repository as it exists now.

---

## 1. Supported Operating Modes

The server supports three runtime modes.

### Managed Neo4j (default)
Use this when Docker is available and you want the server to manage persistence automatically.

Behavior:
- starts a project-scoped Neo4j container automatically;
- persists data in `./.data/neo4j/`;
- reuses the same database on the next session in the same project;
- does not require Neo4j credentials in the MCP client configuration.

### External Neo4j
Use this when you already have a Neo4j service you want to control yourself.

### SQLite
Use this when you want the simplest local setup and do not want Neo4j at all.

---

## 2. Prerequisites

Required:
- Python 3.10+
- `uv`
- Git

Required only for managed Neo4j:
- Docker daemon available and running

Optional:
- Neo4j server, if you choose external Neo4j mode

Install `uv` if necessary:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 3. Clone and Install

```bash
git clone <repository-url>
cd codebase_state_manager_mcp
./scripts/setup.sh
```

The setup script:
- creates `.venv/` with uv;
- installs the package in editable mode;
- installs dev dependencies by default.

Alternative direct install:

```bash
uv sync --extra dev
```

Activate the virtual environment if desired:

```bash
source .venv/bin/activate
```

---

## 4. Start the Server

### Recommended launcher

```bash
python run_mcp_server.py
```

### Alternative module entrypoint

```bash
python -m src.mcp_server
```

### Deprecated compatibility alias

```bash
python init_neo4j_and_mcp.py
```

The alias still works, but the canonical launcher is now `run_mcp_server.py`.

---

## 5. MCP Client Configuration

### 5.1 Minimal configuration for managed Neo4j

```json
{
  "mcp": {
    "codebase-state-manager": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--project",
        "/absolute/path/to/codebase_state_manager_mcp",
        "python",
        "run_mcp_server.py"
      ],
      "enabled": true
    }
  }
}
```

Nothing else is required for Neo4j in this mode.

### 5.2 SQLite mode

```json
{
  "mcp": {
    "codebase-state-manager": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--project",
        "/absolute/path/to/codebase_state_manager_mcp",
        "python",
        "run_mcp_server.py"
      ],
      "environment": {
        "DB_MODE": "sqlite"
      },
      "enabled": true
    }
  }
}
```

### 5.3 External Neo4j mode

```json
{
  "mcp": {
    "codebase-state-manager": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--project",
        "/absolute/path/to/codebase_state_manager_mcp",
        "python",
        "run_mcp_server.py"
      ],
      "environment": {
        "DB_MODE": "neo4j",
        "NEO4J_BOOTSTRAP_MODE": "external",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password"
      },
      "enabled": true
    }
  }
}
```

---

## 6. Environment Variables

The application reads `.env` automatically when present.

### Common

```bash
DB_MODE=neo4j
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=true
AUDIT_ENABLED=true
VOLUME_PATH=/opt/codebase-state-manager/volumes/<current-project-dir-name>
SQLITE_PATH=./data/state_manager.db
```

If `VOLUME_PATH` is omitted, the server automatically falls back to `/opt/codebase-state-manager/volumes/<current-project-dir-name>` so the managed snapshot stays outside the project tree.

### Managed Neo4j

```bash
NEO4J_BOOTSTRAP_MODE=auto
NEO4J_AUTO_IMAGE=neo4j:5.24
NEO4J_AUTO_HOME=./.data/neo4j
NEO4J_CONNECTION_TIMEOUT=90
```

### External Neo4j

```bash
NEO4J_BOOTSTRAP_MODE=external
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

---

## 7. Verification

### Managed Neo4j verification

```bash
docker ps | grep codebase-state-manager-neo4j
ls ./.data/neo4j/
```

### General validation

```bash
python -m pytest tests -q
uv run mypy src/
uv run bandit -r src/ -q
```

Current validation status on the repository:
- tests: `461 passed`
- mypy: pass
- bandit: clean

---

## 8. Development Helpers

### Development runner

```bash
./scripts/dev.sh
```

### Test runner helper

```bash
./scripts/run_tests.sh
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh security
./scripts/run_tests.sh e2e
```

The canonical and most direct command remains:

```bash
python -m pytest tests -q
```

---

## 9. Tooling Notes

### State-returning tools support representation selection
The following tools accept `state_representation`:
- `genesis_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`
- `get_current_state_info_tool`
- `get_state_info_tool`

Accepted values:
- `raw`
- `compact`
- `both`

### Compact preview tool
The server also exposes:
- `get_current_state_compact_context_tool`

This generates an SCC-E (State Compression Code — Embedding) preview for the current workspace without creating a new state.

---

## 10. Troubleshooting

### The server falls back to SQLite unexpectedly
If `DB_MODE=neo4j` and the server cannot connect to Neo4j, it falls back to SQLite.

Check:
- Docker is running for managed Neo4j mode
- your external credentials are correct for external mode
- `NEO4J_BOOTSTRAP_MODE` matches the intended mode

### Managed Neo4j did not start
Check:

```bash
docker ps -a | grep codebase-state-manager-neo4j
ls -R ./.data/neo4j/
```

### SQLite file location
Default SQLite path:

```bash
./data/state_manager.db
```

Override with:

```bash
SQLITE_PATH=/custom/path/state_manager.db
```

---

## 11. Production Recommendations

### Recommended mode
Use **managed Neo4j** when:
- you want graph persistence;
- Docker is available;
- you want the project to carry its own persistent graph database.

### Use SQLite when
- Docker is unavailable;
- you prefer a single local file database;
- operational simplicity is more important than graph-native storage.

### Use external Neo4j when
- your infrastructure already provides Neo4j;
- authentication and backup policies are handled outside the project.

---

## 12. Canonical References

- [README.md](README.md)
- [QUICKSTART.md](QUICKSTART.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CHANGELOG.md](CHANGELOG.md)
