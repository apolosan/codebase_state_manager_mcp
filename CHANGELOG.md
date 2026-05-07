# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-05-07

### Added
- Managed Neo4j bootstrap per project, with persistent runtime/data under `./.data/neo4j/`
- `neo4j_bootstrap_mode = auto | external`
- SCC-E codec module (`src/mcp_server/services/scc_codec.py`)
- Automatic persistence of compact state context on `genesis()` and `new_state_transition()`
- On-demand compact enrichment for legacy states without `llm_context`
- `get_current_state_compact_context_tool`
- `get_compact_states_tool` for single-state, range, and all-state compact retrieval with generating-transition reward when non-null
- `get_rewarded_transitions_tool`
- `set_transition_reward_tool`
- `state_representation = raw | compact | both` support on state-returning tools
- Formal parity tests for SQLite and Neo4j persistence fields
- Launcher configuration tests covering canonical and legacy launchers

### Changed
- Canonical launcher is now `run_mcp_server.py`
- `init_neo4j_and_mcp.py` is now a deprecated compatibility alias
- MCP client examples now use `run_mcp_server.py`
- README, QUICKSTART, SETUP, CONTRIBUTING, and ARCHITECTURE documentation were rewritten to reflect the current codebase and runtime behavior
- Project version bumped to `0.2.1`

### Fixed
- `.gitignore` plain component patterns like `node_modules` and `.next` now match nested paths during managed snapshot copy/sync, preventing oversized volumes and slow transitions in multi-package projects
- Default managed snapshot fallback now uses `/opt/codebase-state-manager/volumes/<current-project-dir-name>` when `VOLUME_PATH` is unset, keeping snapshots outside the project tree by default
- `genesis()` now resolves source and volume paths before the recursion guard check, so relative volume paths inside the project are rejected correctly
- Neo4j current-state lookup now correctly returns state `0` when genesis is the highest existing state and no explicit metadata pointer exists
- SQLite and Neo4j persistence contracts were aligned and revalidated for:
  - compact state fields (`llm_context`, `compression_version`, `compacted_at`)
  - rewarded transitions (`reward`)
- `scripts/run_tests.sh` control flow corrected
- `scripts/dev.sh` logging helper completed
- mypy errors introduced during SCC-E and managed Neo4j work were fixed
- bandit findings introduced by managed Neo4j bootstrap were fixed

### Validation
- `python -m pytest tests -q` → `461 passed`
- `uv run mypy src/` → pass
- `uv run bandit -r src/ -q` → pass

## [0.1.0] - 2026-01-21

### Added
- Initial layered architecture (tools, services, repositories, models, utils)
- Dual repository abstraction for Neo4j and SQLite
- State and transition tracking foundations
- Core MCP operations for state creation, inspection, search, and transition lookup
- Input validation, audit logging, and rate limiting foundations
- Initial Docker and development tooling

