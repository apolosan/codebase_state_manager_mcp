# Recommended Tech Stack for Codebase State Manager MCP Server

## Overview
Based on the specification in `specification_corrected.md`, this report outlines the most suitable technology stack for implementing the Codebase State Manager. The project requires robust Git integration, state and transition tracking (using tuples with hashing), Docker containerization, and a graph database like Neo4j for modeling states as nodes and transitions as edges, with SQLite as a fallback. Key considerations include security, efficiency, ease of integration for AI agents, and compliance with rules like non-duplicate transitions and versioning.

The stack prioritizes Python for its mature libraries in Git operations, graph databases, and scripting, avoiding risks like prototype pollution in Node.js (highlighted in arXiv papers). No exact GitHub matches were found for similar tools, but academic papers emphasize secure state management in runtime environments.

## Programming Language: Python 3.10+
- **Rationale**: Python excels in data manipulation (hashing states with `hashlib`), Git operations (`GitPython`), and database interactions. It's ideal for scripting MCP tools like `genesis()` and `new_state_transition()`. Avoids Node.js vulnerabilities (e.g., prototype pollution leading to RCE, per arXiv:2207.11171). Go is performant but unnecessary for this scripting-focused project.
- **Key Libraries**:
  - `GitPython`: For `git branch`, `git diff HEAD~3`, branch creation (`codebase-state-machine`).
  - `hashlib`: Generate hashes for state tuples.
  - `datetime`: Timestamp transitions.
  - `uuid`: For transition IDs to prevent duplicates.
- **Alternatives Considered**: Node.js (isomorphic-git, but security risks); Go (git2go, overkill for non-performance-critical tasks).

## Database: Neo4j (Primary) with SQLite Fallback
- **Rationale**: Neo4j is perfect for graph modeling: States as nodes (properties: STATE_NUMBER, USER_PROMPT, BRANCH_NAME, GIT_DIFF_INFO, HASH), Transitions as edges (properties: ID, CURRENT_STATE, NEXT_STATE, DATE_TIME). Supports efficient queries like `search_states()` and `track_transitions()`. Official Python driver (`neo4j`) handles async queries, transactions, and Cypher. Fallback to SQLite for relational tuples if graph setup is complex (using SQLAlchemy ORM).
- **Implementation**:
  - Neo4j: Use Cypher for `CREATE` (states/transitions), `MATCH` (get_state_info, search_states), `RETURN` for totals/counters.
  - SQLite: Tables for `states` and `transitions`; enforce unique constraints on transition hashes/IDs.
- **Alternatives Considered**: Pure relational (PostgreSQL, too heavy); In-memory (Redis, lacks persistence for versioning).
- **Security**: Use parameterized Cypher/SQL queries to prevent injection; store no secrets in states.

## Containerization & Deployment: Docker
- **Rationale**: Spec mandates Dockerizing everything, with dedicated volumes for codebase copies (respecting `.gitignore`). Enables isolated environments for state machines and easy versioning.
- **Key Tools**:
  - `Dockerfile`: Base on `python:3.10-slim`; Install Git, Neo4j (via official image or embedded).
  - Volumes: Mount for git repo copy; Use `docker-compose` for Neo4j + app services.
  - Orchestration: Docker Compose (simple); Kubernetes if scaling to multi-project support.
- **Implementation**: `genesis()` clones repo to volume, initializes Neo4j DB.
- **Alternatives Considered**: Podman (less mature); None needed as Docker is specified.

## State Management Pattern: State Machine with Event Sourcing
- **Rationale**: Aligns with spec's state tuples and transitions for unbounded state tracking (no limit on states, using total_states() for counting). General State Machine for arbitrary sequencing (e.g., genesis → new_state_transition → arbitrary_state_transition). Event Sourcing to log immutable changes (prompts, diffs as events), scalable for unlimited history. From design-patterns: Table-Driven State Machine separates logic/data for maintainability (suitable for unbounded states); Event Sourcing ensures auditability (e.g., track last 5 transitions or full history via query).
- **Implementation**: Use `transitions` library (supports hierarchical/unbounded states) or custom class; Store events in Neo4j for efficient replay and querying (`track_transitions()`, `search_states()`). Neo4j scales to millions of nodes/edges for large state graphs.
- **Crazy Idea Integration**: Blockchain (e.g., Ethereum via Web3.py) for immutable transitions – optional, for distributed verification.

## Security & Best Practices
- **Core Principles**: SOLID (Single Responsibility for tools like `get_current_state_info()`), DRY (reusable tuple serializers), KISS (simple hashing/tuples).
- **Security**:
  - Input Sanitization: Validate prompts/diffs (no SQL/Cypher injection via params).
  - Auth/Authz: API keys for MCP tools; RBAC in Neo4j (roles for read/write).
  - Rate Limiting: Throttle transitions to prevent DoS.
  - Secrets: Env vars for Neo4j creds/Docker volumes; Never commit to git.
  - Vulnerabilities: From arXiv (2301.05097), scan Node.js deps if used (but avoided); Use `bandit` for Python security linting.
  - Auditing: Log all transitions; Duplicate prevention via unique hash checks.
- **Performance**: O(1) hash lookups; Index Neo4j on STATE_NUMBER/HASH; SQLite WAL mode for concurrency.
- **Testing/Validation**: 100% coverage with pytest (unit for hashing, integration for git/DB, E2E for Docker flows). Use Spotlight for runtime traces.

## Dependencies
- Core: `GitPython==3.1.40`, `neo4j==5.24.0`, `sqlalchemy==2.0.35` (SQLite).
- Dev: `pytest==8.3.3`, `bandit==1.7.9`, `docker==7.1.0`.
- Docker: Official Neo4j image; Git installed in container.

## Risks & Mitigations
- Graph Overhead: Fallback to SQLite.
- Git Conflicts: Handle merges in `genesis()`.
- Scalability: Container volumes scale per project.

This stack ensures efficient, secure state management aligned with the spec. Future expansions (e.g., UI via shadcn if needed) can build on Python backend.

*Research Sources: arXiv papers on Node.js risks/state tracking; Neo4j Python docs; Design patterns for FSM/Event Sourcing; No direct GitHub analogs found.*