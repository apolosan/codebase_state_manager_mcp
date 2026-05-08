# Architecture

This document describes the **current** architecture of version **0.2.1** of the project.

It reflects the code as implemented today, including:
- managed Neo4j bootstrap;
- SQLite support;
- SCC-E (State Compression Code — Embedding) compact state representation;
- rewarded transitions;
- FastMCP-exposed tools.

---

## 1. System Overview

The project is an MCP server for tracking codebase evolution as a numbered state machine.

A state captures:
- the prompt that motivated a change;
- branch and diff information;
- file-hash snapshots or deltas;
- compact SCC-E (State Compression Code — Embedding) context for LLM consumption.

A transition captures:
- the source state;
- the target state;
- an optional prompt;
- timestamp;
- optional reward.

At runtime, the project supports three storage modes:
- **managed Neo4j** (default);
- **external Neo4j**;
- **SQLite**.

---

## 2. High-Level Flow

```text
MCP client
  ↓
FastMCP tool function (`*_tool`)
  ↓
Tool wrapper in `src/mcp_server/tools/mcp_tools.py`
  ↓
Service layer (`StateService`, `GitManager`, bootstrap services)
  ↓
Repository layer (SQLite or Neo4j)
  ↓
Persistence backend
```

The server entrypoint is:
- canonical: `run_mcp_server.py`
- alternative: `python -m src.mcp_server`
- compatibility alias: `init_neo4j_and_mcp.py`

---

## 3. Startup Architecture

### 3.1 Launchers

#### `run_mcp_server.py`
Canonical launcher. Imports `src.mcp_server.__main__.main` and runs it.

#### `src/mcp_server/__main__.py`
Process-level bootstrap:
- loads settings;
- configures logging, audit, and rate limiting;
- resolves managed Neo4j when applicable;
- builds repositories;
- initializes `StateService`;
- imports the FastMCP app and runs it.

#### `src/mcp_server/mcp_server.py`
Module that builds the FastMCP app and registers all exposed tools.

---

## 4. Configuration Model

Implemented in `src/mcp_server/config.py`.

### 4.1 Primary settings

| Setting | Meaning |
|---|---|
| `db_mode` | `neo4j` or `sqlite` |
| `neo4j_bootstrap_mode` | `auto` or `external` |
| `neo4j_auth_enabled` | Whether Neo4j auth is used |
| `neo4j_auto_image` | Docker image for managed Neo4j |
| `neo4j_auto_home` | Persistent directory for managed Neo4j |
| `sqlite_path` | SQLite database file |
| `volume_path` | Workspace snapshot path |
| `rate_limit_enabled` | Enables/disables rate limiting |
| `audit_enabled` | Enables/disables audit logging |

### 4.2 Mode inference

Behavior today:
- if `DB_MODE` is omitted, the server defaults to `neo4j` when Neo4j is enabled;
- if explicit Neo4j connection variables are present, bootstrap mode resolves to `external`;
- otherwise the server defaults to managed Neo4j bootstrap mode (`auto`).

---

## 5. Managed Neo4j Architecture

Implemented in:
- `src/mcp_server/services/neo4j_service_manager.py`
- `src/mcp_server/services/neo4j_bootstrap.py`

### 5.1 Runtime model

For managed Neo4j mode, the project creates or reuses a **project-scoped** Docker container.

Persistent files live in:

```text
./.data/neo4j/
├── data/
├── logs/
└── runtime.json
```

`runtime.json` stores the resolved runtime state, including:
- container name;
- selected host ports;
- directories;
- image;
- auth mode.

### 5.2 Connection policy

Managed Neo4j runs without auth from the application perspective:
- repository creation uses `auth=None`;
- MCP client configuration does not need Neo4j credentials;
- `prepare_neo4j_connection()` resolves the final runtime URI before repositories are created.

### 5.3 External Neo4j

When `neo4j_bootstrap_mode=external`, startup skips container management and uses the provided connection settings directly.

---

## 6. Core Layers

### 6.1 Tools layer

Primary file:
- `src/mcp_server/tools/mcp_tools.py`

Responsibilities:
- validate tool-level parameters;
- apply rate limiting;
- call service methods;
- serialize state payloads (`raw`, `compact`, `both`);
- emit audit events where appropriate.

### 6.2 Service layer

Primary files:
- `src/mcp_server/services/state_service.py`
- `src/mcp_server/services/git_manager.py`
- `src/mcp_server/services/scc_codec.py`
- `src/mcp_server/services/branch_detection_service.py`
- `src/mcp_server/services/neo4j_bootstrap.py`
- `src/mcp_server/services/neo4j_service_manager.py`

#### `StateService`
Main business orchestrator.

Key responsibilities:
- create genesis state;
- create new state transitions;
- create arbitrary transitions;
- generate and enrich SCC-E compact context;
- expose state and transition queries;
- rebuild and repair the managed volume snapshot;
- update rewards on historical transitions.

#### `GitManager`
Responsibilities:
- clone/sync project snapshots into the managed volume;
- compute directory hashes;
- compute diff and hash deltas;
- initialize repositories in managed snapshots.

#### `scc_codec`
Responsibilities:
- manage path vocabulary metadata;
- generate compact SCC-E payloads;
- build preview payloads for current workspace context.

### 6.3 Repository layer

Primary files:
- `src/mcp_server/repositories/sqlite_repository.py`
- `src/mcp_server/repositories/neo4j_repository.py`
- `src/mcp_server/repositories/abstract_repositories.py`

Responsibilities:
- persist and load `State` objects;
- persist and load `Transition` objects;
- maintain metadata such as current state pointer and SCC-E vocabulary metadata.

---

## 7. Domain Model

### 7.1 `State`
Defined in `src/mcp_server/models/state_model.py`.

This is a regular Python class, **not** a dataclass.

Fields:
- `state_number: int`
- `user_prompt: str`
- `branch_name: str`
- `git_diff_info: str`
- `hash: str`
- `created_at: datetime | None`
- `file_hashes: dict[str, str] | None`
- `file_hash_deltas: dict[str, str | None]`
- `llm_context: str | None`
- `compression_version: str | None`
- `compacted_at: datetime | None`

Serialization is done through:
- `to_dict()`
- `from_dict()`

### 7.2 `Transition`
Also defined in `src/mcp_server/models/state_model.py`.

Fields:
- `transition_id: int`
- `current_state: int`
- `next_state: int`
- `user_prompt: str | None`
- `timestamp: datetime | None`
- `reward: float | None`

Serialization is done through:
- `to_dict()`
- `from_dict()`

---

## 8. Persistence Architecture

## 8.1 SQLite schema

### `states`
Columns:
- `state_number INTEGER PRIMARY KEY`
- `user_prompt TEXT NOT NULL`
- `branch_name VARCHAR(255) NOT NULL`
- `git_diff_info TEXT NULL`
- `hash VARCHAR(64) UNIQUE NOT NULL`
- `created_at DATETIME`
- `file_hashes TEXT NULL`
- `file_hash_deltas TEXT NULL`
- `llm_context TEXT NULL`
- `compression_version VARCHAR(32) NULL`
- `compacted_at DATETIME NULL`

### `transitions`
Columns:
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `current_state INTEGER NOT NULL`
- `next_state INTEGER NOT NULL`
- `user_prompt TEXT NULL`
- `timestamp DATETIME`
- `reward REAL NULL`

### `metadata`
Columns:
- `key VARCHAR(255) PRIMARY KEY`
- `value VARCHAR(255) NOT NULL`

SQLite schema upgrades for new optional columns are handled by:
- `src/mcp_server/utils/schema_upgrade.py`

## 8.2 Neo4j mapping

### `:State` nodes
Properties persisted:
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

### `:TRANSITION` relationships
Properties persisted:
- `transition_id`
- `user_prompt`
- `timestamp`
- `reward`

Endpoints are connected as:

```text
(:State)-[:TRANSITION]->(:State)
```

### `:Metadata` nodes
Used to store:
- current state pointer
- generic metadata values
- SCC-E vocabulary metadata

## 8.3 Parity guarantee

The current implementation keeps logical parity between SQLite and Neo4j for all persisted domain fields.

### `State` parity
Canonical fields persisted in both backends:
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

### `Transition` parity
Canonical fields persisted in both backends:
- `transition_id`
- `current_state`
- `next_state`
- `user_prompt`
- `timestamp`
- `reward`

Implementation detail:
- SQLite uses column `id`
- Neo4j uses property `transition_id`

Both map to the same domain field: `Transition.transition_id`.

---

## 9. State Lifecycle

### 9.1 Genesis

`StateService.genesis()` performs:
1. initialization guard check;
2. source/volume path validation using resolved absolute paths;
3. clone or copy of the project into `VOLUME_PATH/codebase`;
4. local Git repo initialization in the managed snapshot;
5. hash generation of the source project;
6. SCC-E generation for state `0`;
7. persistence of state `0`;
8. current state pointer set to `0`;
9. initialized flag written to the volume root.

### 9.2 New state transition

`StateService.new_state_transition()` performs:
1. initialization check;
2. optional consistency check/repair for SQLite-backed runtime;
3. reconstruction of full previous hashes;
4. diff and hash-delta computation via `GitManager.compute_changes_since_last_state()`;
5. SCC-E generation for the new state;
6. atomic creation of new state + transition + pointer update;
7. sync of the project snapshot back into the managed volume.

### 9.3 Arbitrary transition

`StateService.arbitrary_state_transition()`:
- moves the pointer to an already existing target state;
- records a transition entry;
- enriches the target state with SCC-E if legacy data is missing.

### 9.4 Compact preview

`StateService.get_current_state_compact_context()`:
- compares the current workspace against the current state baseline;
- generates SCC-E preview;
- does **not** persist a new state or transition.

---

## 10. SCC-E Architecture

In the terminology of this project:
- **SCC** means **State Compression Code** — the broader idea of turning verbose state history into a smaller, model-friendly representation.
- **SCC-E** means **State Compression Code — Embedding** — the concrete LLM-facing codec that the current codebase implements.

This distinction matters because the earlier design notes discuss SCC as a general compression family and a simpler baseline, while the running project persists **SCC-E** specifically as compact state context for agents.

Primary file:
- `src/mcp_server/services/scc_codec.py`

### 10.1 Stored fields
Compact state metadata is stored in the `State` model itself:
- `llm_context`
- `compression_version`
- `compacted_at`

### 10.2 Vocabulary metadata
The shared path vocabulary is stored in repository metadata using:
- `scc_e_path_vocab`
- `scc_e_vocab_revision`
- `scc_e_vocab_format`

### 10.3 Representation strategy
State-returning tools support:
- `raw`
- `compact`
- `both`

This is implemented in the tool layer, not the repositories.

### 10.4 Legacy state enrichment
If an old state does not have compact fields, `StateService._ensure_compact_state_context()` generates SCC-E on demand using persisted diffs and hashes.

### 10.5 Compact state queries with reward context
`StateService.get_compact_states()`:
- returns persisted compact payloads for one state, an inclusive range, or all states;
- enriches legacy states with SCC-E when needed;
- attaches the reward from the earliest transition that produced each state;
- omits the `reward` field when the generating transition has `reward = null`.

---

## 11. Tool Surface

The FastMCP app currently exposes **25** tools.

### Lifecycle and state tools
- `genesis_tool`
- `start_genesis_tool`
- `get_genesis_status_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`
- `get_current_state_number_tool`
- `get_current_state_info_tool`
- `get_state_info_tool`
- `total_states_tool`
- `search_states_tool`

### Transition tools
- `get_state_transitions_tool`
- `get_transition_info_tool`
- `track_transitions_tool`
- `get_current_state_transitions_tool`
- `get_rewarded_transitions_tool`
- `set_transition_reward_tool`

### Compact context tools
- `get_current_state_compact_context_tool`
- `get_compact_states_tool`

### Volume and consistency tools
- `fix_volume_path_tool`
- `start_fix_volume_path_tool`
- `get_fix_volume_path_status_tool`
- `get_fix_volume_path_result_tool`
- `check_consistency_tool`
- `repair_consistency_tool`

---

## 12. Volume Snapshot Architecture

The project keeps a managed workspace snapshot under:

```text
VOLUME_PATH/codebase
```

When `VOLUME_PATH` is not explicitly configured, the runtime default is:

```text
/opt/codebase-state-manager/volumes/<current-project-dir-name>/codebase
```

This snapshot is used to:
- compute diffs against the current project;
- support recovery when the live project and persisted state diverge;
- rebuild a consistent working copy.

### `fix_volume_path()`
This service method:
- validates consistency first;
- identifies the managed project path;
- verifies snapshot divergence;
- may create a recovery transition when necessary;
- rebuilds the managed volume snapshot;
- rechecks consistency.

---

## 13. Security and Validation

### Input validation
Primary file:
- `src/mcp_server/utils/validation.py`

Includes validation for:
- prompts
- paths
- state ranges
- transition ids
- reward values
- SCC-E payload structure

### Rate limiting
Primary file:
- `src/mcp_server/utils/security.py`

Current algorithm:
- **sliding window**, in-memory

This replaces older documentation that described token bucket behavior.

### Audit logging
Primary file:
- `src/mcp_server/utils/audit.py`

Tracks:
- state transitions
- arbitrary transitions
- genesis
- reward updates
- validation failures
- rate-limit events
- security events

---

## 14. Testing and Validation Architecture

Current repository validation commands:

```bash
python -m pytest tests -q
uv run mypy src/
uv run bandit -r src/ -q
```

Validation status on the current codebase:
- tests: `461 passed`
- mypy: pass
- bandit: clean

---

## 15. Key Operational Guarantees

The current codebase guarantees:
- backend parity for domain persistence fields;
- canonical launcher stability via `run_mcp_server.py`;
- managed Neo4j persistence across sessions in the same project;
- SCC-E persistence on newly created states;
- compact preview without mutation;
- reward persistence and historical reward updates.
