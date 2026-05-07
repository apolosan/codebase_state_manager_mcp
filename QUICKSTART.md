# Quick Start

This guide shows the shortest correct path to run the project today.

Current validated project version: **0.2.1**.

---

## 1. Prerequisites

Required:
- Python 3.10+
- `uv`
- Git

Required only for the default managed Neo4j mode:
- Docker running locally

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Install

```bash
git clone <repository-url>
cd codebase_state_manager_mcp
./scripts/setup.sh
```

Alternative:

```bash
uv sync --extra dev
```

---

## 3. Start the server locally

Recommended launcher:

```bash
python run_mcp_server.py
```

Alternative:

```bash
python -m src.mcp_server
```

Legacy compatibility alias still exists, but is deprecated:

```bash
python init_neo4j_and_mcp.py
```

---

## 4. Minimal MCP client configuration

### Default: managed Neo4j

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

This mode does **not** require:
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

---

## 5. Optional runtime modes

### SQLite

```json
{
  "env": {
    "DB_MODE": "sqlite"
  }
}
```

### External Neo4j

```json
{
  "env": {
    "DB_MODE": "neo4j",
    "NEO4J_BOOTSTRAP_MODE": "external",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "your_password"
  }
}
```

---

## 6. Verify the setup

### Managed Neo4j mode

```bash
docker ps | grep codebase-state-manager-neo4j
ls ./.data/neo4j/
```

### Full validation

```bash
python -m pytest tests -q
uv run mypy src/
uv run bandit -r src/ -q
```

Latest validation result on the current codebase:
- `461 passed`
- `mypy` passing
- `bandit` clean

---

## 7. Main exposed MCP tools

- `genesis_tool`
- `new_state_transition_tool`
- `get_current_state_info_tool`
- `get_current_state_compact_context_tool`
- `get_rewarded_transitions_tool`
- `set_transition_reward_tool`
- `fix_volume_path_tool`
- `check_consistency_tool`
- `repair_consistency_tool`

For the full list and exact semantics, see [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
