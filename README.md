# Codebase State Manager MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-461%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-85%25-green.svg)]()
[![mypy](https://img.shields.io/badge/mypy-passing-green.svg)]()
[![Bandit](https://img.shields.io/badge/Bandit-clean-green.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)]()
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()

A production-ready Model Context Protocol (MCP) server for managing codebase states as numbered snapshots and transitions, with Git-aware diffs, SCC-E compact context for LLM workflows, rewarded transitions, automatic project-scoped Neo4j bootstrap, external Neo4j support, SQLite fallback, and managed workspace snapshot recovery.

## Current Validation Status

Validation executed on the current codebase:

| Check | Result |
|---|---|
| Test suite | `461 passed` |
| Type checking | `uv run mypy src/` → pass |
| Security scan | `uv run bandit -r src/ -q` → pass |

The skipped tests are integration cases that depend on specific external runtime conditions.

---

## What the Server Does

The server maintains a numbered history of project states.

Each state stores:
- the user prompt that motivated the change;
- branch information;
- textual change information (`git_diff_info`);
- file-hash snapshots or deltas;
- SCC-E compact context (`llm_context`, `compression_version`, `compacted_at`).

Each transition stores:
- source state;
- destination state;
- user prompt;
- timestamp;
- optional `reward`.

This allows LLM agents and other consumers to:
- register new transitions;
- inspect the current or historical state;
- preview compact context before persisting;
- re-score historical transitions;
- rebuild and verify the managed workspace volume.

---

## Supported Database Modes

### 1. Managed Neo4j (default)
When `DB_MODE=neo4j` and no explicit Neo4j connection is provided, the server:

- starts a **project-scoped Neo4j container automatically**;
- stores persistent Neo4j data in `./.data/neo4j/`;
- stores runtime metadata in `./.data/neo4j/runtime.json`;
- reuses the same container and data on the next session in the same project;
- connects without requiring `NEO4J_URI`, `NEO4J_USER`, or `NEO4J_PASSWORD` in MCP client configuration.

### 2. External Neo4j
If you want to use an already existing Neo4j instance, set:

- `DB_MODE=neo4j`
- `NEO4J_BOOTSTRAP_MODE=external`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

### 3. SQLite
If you want a self-contained local database without Neo4j, set:

- `DB_MODE=sqlite`

SQLite data is stored by default at:
- `./data/state_manager.db`

---

## Installation

### Prerequisites

Required:
- Python **3.10+**
- `uv`
- Git

Required only for managed Neo4j mode:
- Docker daemon running locally

Install `uv` if necessary:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone and install

```bash
git clone <repository-url>
cd codebase_state_manager_mcp
./scripts/setup.sh
```

Alternative direct install with uv:

```bash
uv sync --extra dev
```

Optional: activate the virtual environment created by `setup.sh`:

```bash
source .venv/bin/activate
```

---

## Starting the Server

### Recommended launcher

```bash
python run_mcp_server.py
```

### Alternative module entrypoint

```bash
python -m src.mcp_server
```

### Legacy compatibility launcher

This file still exists for backward compatibility only:

```bash
python init_neo4j_and_mcp.py
```

Prefer `run_mcp_server.py` for all new integrations.

---

## MCP Client Configuration

### Minimal configuration: managed Neo4j

This is the recommended MCP client configuration.

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

No Neo4j credentials are required in the MCP client config for this mode.

If `VOLUME_PATH` is omitted, the server automatically uses:

```text
/opt/codebase-state-manager/volumes/<current-project-dir-name>
```

This keeps the managed snapshot outside the project tree by default.

### SQLite configuration

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

### External Neo4j configuration

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

## Environment Variables

The server reads `.env` automatically when present.

### Common variables

| Variable | Default | Meaning |
|---|---|---|
| `DB_MODE` | `neo4j` | `neo4j` or `sqlite` |
| `LOG_LEVEL` | `INFO` | Logging level |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `AUDIT_ENABLED` | `true` | Enable audit logging |
| `VOLUME_PATH` | `/opt/codebase-state-manager/volumes/<current-project-dir-name>` | Managed workspace snapshot path |
| `SQLITE_PATH` | `./data/state_manager.db` | SQLite database path |

When `VOLUME_PATH` is not set, the server derives the final directory name from `Path.cwd().name`, so a project opened from `/workspace/my-app` defaults to `/opt/codebase-state-manager/volumes/my-app`.

### Managed Neo4j variables

| Variable | Default | Meaning |
|---|---|---|
| `NEO4J_BOOTSTRAP_MODE` | inferred / `auto` | `auto` or `external` |
| `NEO4J_AUTO_IMAGE` | `neo4j:5.24` | Docker image used for managed Neo4j |
| `NEO4J_AUTO_HOME` | `./.data/neo4j` | Directory containing Neo4j runtime/data/logs |
| `NEO4J_CONNECTION_TIMEOUT` | `90` | Neo4j connection timeout in seconds |

### External Neo4j variables

Used only when `NEO4J_BOOTSTRAP_MODE=external`.

| Variable | Meaning |
|---|---|
| `NEO4J_URI` | Bolt connection URI |
| `NEO4J_USER` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `NEO4J_AUTH_ENABLED` | Optional explicit auth toggle |

---

## Exposed MCP Tools

The actual tool names exposed by the FastMCP server are the `*_tool` names below.

### State and lifecycle
- `genesis_tool`
- `start_genesis_tool`
- `get_genesis_status_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`
- `get_current_state_info_tool`
- `get_state_info_tool`
- `get_current_state_number_tool`
- `total_states_tool`
- `search_states_tool`

### Transition inspection and rewards
- `get_state_transitions_tool`
- `get_transition_info_tool`
- `track_transitions_tool`
- `get_current_state_transitions_tool`
- `get_rewarded_transitions_tool`
- `set_transition_reward_tool`

### Compact context
- `get_current_state_compact_context_tool`
- `get_compact_states_tool`

### Volume repair and consistency
- `fix_volume_path_tool`
- `start_fix_volume_path_tool`
- `get_fix_volume_path_status_tool`
- `get_fix_volume_path_result_tool`
- `check_consistency_tool`
- `repair_consistency_tool`

Total exposed MCP tools: **25**.

---

## State Representations

Tools that return a `State` support:

- `raw` — full legacy payload (default)
- `compact` — only compact SCC-E view
- `both` — both representations together

Supported today on:
- `genesis_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`
- `get_current_state_info_tool`
- `get_state_info_tool`

Compact state payload fields:
- `state_number`
- `llm_context`
- `compression_version`
- `compacted_at`

---

## SCC-E Compact Context

The project uses SCC-E to store compact, LLM-oriented state representations.

Current behavior:
- persisted automatically on `genesis()` and `new_state_transition()`;
- generated on demand for legacy states that do not have compact context yet;
- available through `get_current_state_compact_context_tool` without creating a new state;
- queryable in persisted form through `get_compact_states_tool` for one state, an inclusive state range, or all states.

The preview tool returns:
- current state number;
- compact payload;
- vocabulary revision;
- optional vocabulary map;
- `persisted: false`.

The persisted compact-state tool returns:
- compact state payloads (`state_number`, `llm_context`, `compression_version`, `compacted_at`);
- the reward from the earliest transition that produced each state, only when that reward is non-null.

---

## Persistence Parity: SQLite and Neo4j

The project keeps the same logical persistence contract across both backends.

### State fields persisted in both backends
- `state_number`
- `user_prompt`
- `branch_name`
- `git_diff_info`
- `hash`
- `created_at`
- `file_hashes`
- `file_hash_deltas`
- `llm_context`
- `compression_version`
- `compacted_at`

### Transition fields persisted in both backends
- `transition_id`
- `current_state`
- `next_state`
- `user_prompt`
- `timestamp`
- `reward`

Implementation difference:
- SQLite stores transition primary key as column `id`
- Neo4j stores transition identifier as property `transition_id`

At the model and service layers, both map to the same domain field: `Transition.transition_id`.

---

## Testing and Quality Commands

### Full test suite

```bash
python -m pytest tests -q
```

### Helper script

```bash
./scripts/run_tests.sh
```

### Static checks

```bash
uv run mypy src/
uv run bandit -r src/ -q
```

### Development runner

```bash
./scripts/dev.sh
```

---

## Recommended Production Modes

### Recommended default
Use **managed Neo4j** when:
- Docker is available
- you want graph persistence without extra manual setup
- you want project-scoped persistence that survives across sessions

### Use SQLite when
- Docker is not available
- you want the simplest local setup
- graph traversal features are not critical for your workflow

### Use external Neo4j when
- you already operate a shared Neo4j service
- you need your own backup, security, and infrastructure policies

---

## Notes on Docker

The repository still contains Docker Compose files for local and test scenarios, but the recommended runtime path for the MCP server is now:

- `run_mcp_server.py`
- `python -m src.mcp_server`

For managed Neo4j mode, the application itself handles Neo4j lifecycle automatically.

---

## Additional Documentation

- [QUICKSTART.md](QUICKSTART.md) — minimal setup and MCP client configuration
- [SETUP.md](SETUP.md) — detailed installation and configuration guide
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture and storage mapping
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributor workflow and validation checklist
- [CHANGELOG.md](CHANGELOG.md) — release history
- [AGENTS.md](AGENTS.md) — repository operating instructions for coding agents

---

## License

MIT. See [LICENSE](LICENSE).
