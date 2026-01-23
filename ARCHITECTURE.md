# Architecture

This document describes the system architecture of the Codebase State Manager MCP Server.

## Overview

The system follows **Clean Architecture** principles with a layered structure that separates concerns and ensures testability, maintainability, and flexibility.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Client (Opencode)                      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Tools Layer                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐   │
│  │   genesis   │ │new_state_   │ │ arbitrary_state_        │   │
│  │             │ │transition   │ │ transition              │   │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐   │
│  │get_current_ │ │ get_state_  │ │ search_states           │   │
│  │state_info   │ │ info        │ │                         │   │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Services Layer (Business Logic)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    StateService                         │   │
│  │  - genesis()                                            │   │
│  │  - new_state_transition()                               │   │
│  │  - arbitrary_state_transition()                         │   │
│  │  - get_current_state()                                  │   │
│  │  - search_states()                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    GitManager                           │   │
│  │  - run_git_command()                                    │   │
│  │  - get_branch_name()                                    │   │
│  │  - get_diff()                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Repositories Layer (Data Access)                │
│  ┌───────────────────┐  ┌───────────────────────────────────┐   │
│  │  StateRepository  │  │      TransitionRepository         │   │
│  │  (Abstract)       │  │      (Abstract)                   │   │
│  └─────────┬─────────┘  └───────────────────┬───────────────┘   │
│            │                                │                    │
│    ┌───────┴───────┐              ┌─────────┴─────────┐         │
│    ▼               ▼              ▼                   ▼         │
│ ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐ │
│ │  Neo4j   │  │ SQLite   │  │    Neo4j     │  │    SQLite    │ │
│ │ Repository│ │ Repository│  │ Repository   │  │ Repository   │ │
│ └──────────┘  └──────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Persistence Layer (Database)                     │
│  ┌─────────────────────┐           ┌─────────────────────────┐  │
│  │     Neo4j           │           │      SQLite             │  │
│  │  (Primary)          │           │      (Fallback)         │  │
│  └─────────────────────┘           └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

                            ┌─────────────┐
                            │    Docker   │
                            │  Container  │
                            └─────────────┘
```

## Layer Descriptions

### MCP Tools Layer (`src/mcp_server/tools/`)

The entry point for all MCP tool calls. Each tool:
- Validates input parameters
- Calls the appropriate service method
- Returns formatted results to the client

### Services Layer (`src/mcp_server/services/`)

Contains business logic and orchestrates operations:

- **StateService**: Core state machine logic
  - Manages state transitions (genesis, new, arbitrary)
  - Enforces uniqueness constraints
  - Generates state hashes

- **GitManager**: Git operations
  - Executes git commands in containers
  - Handles timeouts and errors
  - Provides branch and diff information

### Repositories Layer (`src/mcp_server/repositories/`)

Abstract data access layer with concrete implementations:

- **StateRepository**: CRUD for states
- **TransitionRepository**: CRUD for transitions

Two implementations:
1. **Neo4j**: Graph database for states and transitions
2. **SQLite**: Relational database fallback

### Persistence Layer

- **Neo4j**: Primary database using Cypher queries
  - States as nodes with properties
  - Transitions as edges

- **SQLite**: Fallback using SQLAlchemy
  - Relational tables with constraints

## Data Models (`src/mcp_server/models/`)

### State

```python
@dataclass
class State:
    state_number: int          # Unique state identifier
    user_prompt: str           # Original user prompt
    branch_name: str           # Git branch name
    git_diff_info: str         # Git diff content
    hash: str                  # SHA256 hash of state content
    created_at: datetime       # Creation timestamp
```

### Transition

```python
@dataclass
class Transition:
    transition_id: UUID        # Unique transition ID
    current_state: int         # Source state number
    next_state: int            # Target state number
    user_prompt: str           # Transition prompt
    timestamp: datetime        # When transition occurred
```

## Utilities (`src/mcp_server/utils/`)

| Module | Purpose |
|--------|---------|
| `validation.py` | Input sanitization and validation |
| `logging.py` | Structured JSON logging |
| `metrics.py` | Performance monitoring |
| `security.py` | Security utilities (rate limiting, audit) |
| `hash.py` | State hashing utilities |
| `audit.py` | Audit logging for security events |

## Container Architecture

### Docker Container

```
┌──────────────────────────────────────────────────────────────┐
│                    Docker Container                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  Python Application                      │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │  │
│  │  │ MCP Server  │ │ StateService│ │   GitManager    │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Neo4j Database                       │  │
│  │  (Optional, can be external)                            │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   Docker Volume                         │  │
│  │  - Codebase copy                                        │  │
│  │  - State data                                           │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Docker Compose Configurations

1. **Embedded Mode** (default): Neo4j runs in the same container
2. **External Mode**: Neo4j runs in a separate container

## Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Security Layers                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Input Validation & Sanitization                       │  │
│  │  - sanitize_prompt()                                   │  │
│  │  - validate_path()                                     │  │
│  │  - validate_state_number()                             │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Rate Limiting                                         │  │
│  │  - Token bucket algorithm                              │  │
│  │  - Per-client limiting                                 │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Audit Logging                                         │  │
│  │  - All operations logged                               │  │
│  │  - Security violations tracked                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Access Control                                        │  │
│  │  - Environment-based configuration                     │  │
│  │  - No hardcoded secrets                                │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## State Machine Flow

```
genesis() → State #0 → new_state_transition() → State #1
                                            ↓
                              new_state_transition() → State #2
                                            ↓
                              arbitrary_state_transition(0) → State #0
```

## Error Handling

```
┌──────────────────────────────────────────────────────────────┐
│                    Exception Hierarchy                        │
│                                                              │
│  StateServiceError (base)                                   │
│  ├── StateNotFoundError                                     │
│  ├── InvalidStateTransitionError                            │
│  ├── ValidationError                                        │
│  │   ├── InvalidPromptError                                 │
│  │   ├── InvalidPathError                                   │
│  │   └── InvalidStateNumberError                            │
│  ├── GitOperationError                                      │
│  │   ├── GitTimeoutError                                    │
│  │   └── GitCloneError                                      │
│  └── DatabaseError                                          │
│      ├── Neo4jConnectionError                               │
│      └── SQLiteError                                        │
└──────────────────────────────────────────────────────────────┘
```

## Dependencies

External dependencies flow inward:

```
MCP Client → Tools → Services → Repositories → Database
                            ↓
                     Utilities
```

This ensures:
- **Testability**: Mock any layer for testing
- **Flexibility**: Swap implementations without changing upper layers
- **Maintainability**: Clear separation of concerns
