# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-21

### Added

- **Core Architecture**
  - Clean Architecture with layered structure (tools, services, repositories, models, utils)
  - Abstract base classes for repositories (StateRepository, TransitionRepository)
  - Concrete implementations for Neo4j and SQLite databases
  - State and Transition data models with serialization

- **Core Tools (MCP)**
  - `genesis()`: Initialize state machine with state #0
  - `new_state_transition()`: Automatic state transitions with hashing
  - `arbitrary_state_transition()`: Jump to any state
  - `get_current_state_number()`: Get current state number
  - `get_current_state_info()`: Get full context of current state
  - `get_state_info()`: Get info for any state
  - `get_state_transitions()`: Get transitions for a state
  - `get_transition_info()`: Get transition details
  - `search_states()`: Full-text search in prompts
  - `track_transitions()`: Get last 5 transitions
  - `total_states()`: Get total state count

- **Security**
  - Input validation and sanitization (CWE-78, CWE-22 mitigation)
  - Path traversal prevention
  - OS command injection prevention
  - Rate limiting support
  - Defense in depth strategy

- **Performance & Monitoring**
  - Structured JSON logging
  - Performance metrics collection
  - Timer utilities
  - Performance thresholds monitoring

- **Development Tools**
  - UV package manager support
  - Poetry configuration
  - Comprehensive test suite (144 tests)
  - Docker containerization
  - Pre-commit hooks configuration

### Changed

- Updated to Python 3.10+ for type safety
- Refactored validation utilities for better error messages
- Improved error handling with specific exception types
- Transition ID now uses sequential integers instead of UUIDs for clearer state machine representation

### Fixed

- Atomic state transitions with rollback on failure
- Proper session and state context in logging
- **Transition ID format**: Transition IDs changed from UUID (e.g., `45008f11-6351-438a-8ebc-83613b7a6379`) to sequential integers (1, 2, 3...) for better traceability and consistent state machine representation
  - `Transition.transition_id` type changed from `UUID` to `int`
  - Sequential IDs generated via `transition_repo.count() + 1`
  - SQLite `TransitionModel.id` column type changed from `String(36)` to `Integer`
  - Neo4j transition `transition_id` stored as Integer instead of String
  - `get_by_id()` methods now accept `int` instead of `UUID`
  - Affected files: `state_model.py`, `abstract_repositories.py`, `neo4j_repository.py`, `sqlite_repository.py`, `state_service.py`

### Security

- Validated all user inputs
- Sanitized git operations
- Protected against injection attacks

## [0.0.1] - 2026-01-20

### Added

- Initial project structure
- Basic Docker configuration
- Git integration

## TODO

- Add configuration management
- Add monitoring dashboard
- Add state export/import
- Add team collaboration features

[0.1.0]: https://github.com/anomalyco/codebase_state_manager_mcp/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/anomalyco/codebase_state_manager_mcp/releases/tag/v0.0.1
