# AGENTS.md - Codebase State Manager MCP Server

This document provides comprehensive guidelines for agentic coding assistants working on the Codebase State Manager MCP Server project. It covers build/lint/test commands, code style guidelines, and operational requirements.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Development Environment Setup](#development-environment-setup)
4. [Build and Development Commands](#build-and-development-commands)
5. [Testing Commands](#testing-commands)
6. [Code Quality and Linting](#code-quality-and-linting)
7. [Code Style Guidelines](#code-style-guidelines)
8. [Architecture Guidelines](#architecture-guidelines)
9. [Security Guidelines](#security-guidelines)
10. [Performance Guidelines](#performance-guidelines)
11. [Error Handling](#error-handling)
12. [Testing Guidelines](#testing-guidelines)
13. [Documentation Guidelines](#documentation-guidelines)
14. [Git and Version Control](#git-and-version-control)
15. [Database and Persistence](#database-and-persistence)
16. [Codebase State Manager Tool Integration](#codebase-state-manager-tool-integration)

## Project Overview

Codebase State Manager is an MCP (Model Context Protocol) server that manages codebase states with Git integration, supporting both Neo4j and SQLite backends. It tracks state transitions, provides Git operations, and offers comprehensive state management capabilities.

## Technology Stack

- **Python**: 3.10 or higher
- **MCP Framework**: FastMCP for Model Context Protocol
- **Database**: Neo4j (primary) or SQLite (fallback)
- **Git Integration**: GitPython
- **ORM**: SQLAlchemy
- **Dependency Management**: Poetry/uv
- **Testing**: pytest with coverage
- **Type Checking**: mypy
- **Code Quality**: black, isort, bandit, ruff

## Development Environment Setup

### Prerequisites
- Python 3.10+
- Git
- uv (recommended) or Poetry
- Docker (for Neo4j integration tests)

### Setup Commands
```bash
# Clone and setup
git clone <repository-url>
cd codebase_state_manager_mcp

# Install dependencies with uv (recommended)
uv pip install -e .[dev]

# Or with Poetry
poetry install

# Activate virtual environment
source .venv/bin/activate

# Verify installation
uv run python -c "import mcp_server; print('Setup successful')"
```

## Build and Development Commands

### Package Building
```bash
# Build package
python -m build

# Build with Poetry
poetry build

# Install in development mode
uv pip install -e .
poetry install
```

### Running the Application
```bash
# Run MCP server
uv run python -m src.mcp_server

# Run with specific config
DB_MODE=sqlite uv run python -m src.mcp_server

# Development mode with auto-reload
uv run python -m src.mcp_server --reload
```

### Pre-commit Checks
```bash
# Run all pre-commit checks manually
.git/hooks/pre-commit

# Individual checks
uv run black --check src/
uv run isort --check src/
uv run mypy src/
uv run bandit -r src/
uv run pytest tests/unit/ -v
```

## Testing Commands

### Running Tests
```bash
# All tests
uv run pytest tests/

# Unit tests only
uv run pytest tests/unit/

# Integration tests (requires Neo4j)
uv run pytest tests/integration/

# Security tests
uv run pytest tests/security/

# Performance tests
uv run pytest tests/performance/

# End-to-end tests
uv run pytest tests/e2e/
```

### Test Options
```bash
# With coverage report
uv run pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

# Verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/unit/test_state_service.py -v

# Run single test function
uv run pytest tests/unit/test_state_service.py::TestStateService::test_create_state -v

# Run tests matching pattern
uv run pytest -k "test_create" -v

# Stop on first failure
uv run pytest tests/ -x

# Run with debugging
uv run pytest tests/ --pdb
```

### Test Structure
```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── security/       # Security-focused tests
├── performance/    # Performance tests
├── e2e/           # End-to-end tests
├── stress/        # Stress/load tests
└── conftest.py    # Test configuration and fixtures
```

## Code Quality and Linting

### Automated Quality Checks
```bash
# Type checking
uv run mypy src/

# Code formatting check
uv run black --check src/
uv run isort --check src/

# Security analysis
uv run bandit -r src/

# General linting
uv run ruff check src/

# Fix formatting automatically
uv run black src/
uv run isort src/
uv run ruff check src/ --fix
```

### Quality Gates
- **Type Coverage**: 100% (mypy strict mode)
- **Test Coverage**: Minimum 80%
- **Security**: Zero high/critical bandit issues
- **Formatting**: black + isort compliance
- **Linting**: Zero ruff errors

## Code Style Guidelines

### General Principles
- **Type Safety First**: All functions and methods must have type hints
- **Explicit over Implicit**: Prefer explicit code over clever shortcuts
- **Fail Fast**: Validate inputs early and raise descriptive errors
- **Single Responsibility**: Each class/function should do one thing well
- **DRY Principle**: Don't Repeat Yourself
- **SOLID Principles**: Follow SOLID design principles

### Naming Conventions
```python
# Classes
class StateService:           # PascalCase
class GitManager:            # PascalCase

# Functions and methods
def create_state():          # snake_case
def validate_input():        # snake_case
def get_current_state():     # snake_case

# Variables
state_number: int           # snake_case
current_state: State        # snake_case
is_valid: bool             # snake_case

# Constants
MAX_RETRIES = 3            # UPPER_SNAKE_CASE
DEFAULT_TIMEOUT = 30       # UPPER_SNAKE_CASE

# Private attributes
self._state_repo           # Leading underscore
self.__audit_logger        # Double underscore (name mangling)
```

### Import Organization
```python
# Standard library imports (alphabetical)
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Third-party imports (alphabetical)
from neo4j import GraphDatabase
import sqlalchemy as sa

# Local imports (grouped by module)
from .config import Settings
from .models.state_model import State, Transition
from .repositories.abstract_repositories import StateRepository
from .utils.validation import ValidationError, sanitize_input
```

### Type Hints
```python
# Function signatures
def create_state(self, user_prompt: str, settings: Settings) -> State:
    """Create a new state with the given prompt."""

# Generic types
from typing import Dict, List, Optional, Union, Any

def process_states(self, states: List[State]) -> Dict[str, Any]:
    """Process a list of states and return results."""

# Complex types
StateDict = Dict[str, Union[str, int, float]]
OptionalState = Optional[State]
```

### Docstrings
Use Google-style docstrings:

```python
def create_state(self, user_prompt: str, settings: Settings) -> State:
    """Create a new state with the given prompt.

    Args:
        user_prompt: The user-provided prompt describing the state.
        settings: Application settings for state creation.

    Returns:
        The newly created State object.

    Raises:
        ValidationError: If the user_prompt is invalid.
        StateServiceError: If state creation fails.

    Example:
        >>> state = service.create_state("Initial state", settings)
        >>> print(state.state_number)
        1
    """
```

### Code Structure
```python
# Class definition with proper spacing
class StateService:
    """Service for managing codebase states."""

    def __init__(
        self,
        state_repo: StateRepository,
        transition_repo: TransitionRepository,
        git_manager: GitManager,
        settings: Settings,
    ) -> None:
        """Initialize the StateService.

        Args:
            state_repo: Repository for state persistence.
            transition_repo: Repository for transition persistence.
            git_manager: Git operations manager.
            settings: Application configuration.
        """
        self.state_repo = state_repo
        self.transition_repo = transition_repo
        self.git_manager = git_manager
        self.settings = settings
        self._audit_logger = get_audit_logger()

    def create_state(self, user_prompt: str) -> State:
        """Create a new state."""
        # Input validation
        if not user_prompt or not user_prompt.strip():
            raise ValidationError("User prompt cannot be empty")

        # Business logic
        sanitized_prompt = sanitize_prompt(user_prompt)
        state_hash = generate_state_hash(sanitized_prompt)

        # Create state object
        state = State(
            state_number=self._get_next_state_number(),
            user_prompt=sanitized_prompt,
            state_hash=state_hash,
            created_at=datetime.now(timezone.utc),
        )

        # Persist state
        if not self.state_repo.create(state):
            raise StateServiceError("Failed to create state")

        # Log operation
        self._audit_logger.info(f"Created state {state.state_number}")

        return state
```

## Architecture Guidelines

### Clean Architecture Layers
```
src/mcp_server/
├── tools/          # MCP tool definitions (interface layer)
├── services/       # Business logic (use case layer)
├── repositories/   # Data access (infrastructure layer)
├── models/         # Data models (entities)
└── utils/          # Shared utilities (framework layer)
```

### Service Layer Responsibilities
- **StateService**: Core business logic for state management
- **GitManager**: Git operations and repository management
- Validation, security, and audit logging

### Repository Pattern
- Abstract repository interfaces in `repositories/abstract_repositories.py`
- Concrete implementations for Neo4j and SQLite
- Dependency injection for testability

### Error Handling Hierarchy
```python
# Base exceptions
class StateServiceError(Exception):
    """Base exception for StateService operations."""

# Specific exceptions
class StateNotFoundError(StateServiceError):
    """Raised when a requested state is not found."""

class InvalidStateTransitionError(StateServiceError):
    """Raised when a state transition is invalid."""

class GitOperationError(StateServiceError):
    """Raised when Git operations fail."""
```

## Security Guidelines

### Input Validation
```python
from .utils.validation import sanitize_prompt, validate_state_number

def create_state(self, user_prompt: str) -> State:
    """Create a new state with security validation."""
    # Sanitize input
    sanitized = sanitize_prompt(user_prompt)

    # Validate length and content
    if len(sanitized) > 1000:
        raise ValidationError("Prompt too long")

    # Check for malicious patterns
    if contains_sql_injection(sanitized):
        raise SecurityError("Invalid input detected")
```

### Rate Limiting
```python
from .utils.security import get_rate_limiter

def create_state(self, user_prompt: str) -> State:
    """Create state with rate limiting."""
    rate_limiter = get_rate_limiter()

    if not rate_limiter.allow_request():
        raise RateLimitExceeded("Too many requests")

    # Proceed with state creation
    return self._create_state_internal(user_prompt)
```

### Audit Logging
```python
from .utils.audit import get_audit_logger

def create_state(self, user_prompt: str) -> State:
    """Create state with audit logging."""
    logger = get_audit_logger()

    try:
        state = self._create_state_internal(user_prompt)
        logger.info(f"State {state.state_number} created successfully")
        return state
    except Exception as e:
        logger.error(f"Failed to create state: {e}")
        raise
```

## Performance Guidelines

### Database Optimization
- Use connection pooling for Neo4j/SQLite
- Implement proper indexing strategies
- Batch operations when possible
- Monitor query performance

### Memory Management
```python
# Use context managers for resource cleanup
with self.state_repo.transaction() as tx:
    state = tx.create_state(state_data)
    transition = tx.create_transition(transition_data)
    tx.commit()
```

### Caching Strategies
- Cache frequently accessed states
- Implement TTL (Time To Live) for cache entries
- Invalidate cache on state modifications

## Error Handling

### Exception Patterns
```python
try:
    state = self.state_repo.get_by_number(state_number)
    if not state:
        raise StateNotFoundError(f"State {state_number} not found")
    return state
except DatabaseConnectionError as e:
    logger.error(f"Database connection failed: {e}")
    raise StateServiceError("Service temporarily unavailable") from e
except ValidationError as e:
    # Don't log validation errors (expected)
    raise
except Exception as e:
    logger.error(f"Unexpected error in get_state: {e}")
    raise StateServiceError("Internal error") from e
```

### Error Messages
- Be descriptive but don't leak sensitive information
- Include context (operation, parameters)
- Use error codes for programmatic handling
- Log full stack traces internally

## Testing Guidelines

### Test Structure
```python
import pytest
from unittest.mock import MagicMock, patch

class TestStateService:
    """Test cases for StateService."""

    @pytest.fixture
    def mock_repo(self):
        """Mock repository for testing."""
        return MagicMock(spec=StateRepository)

    @pytest.fixture
    def service(self, mock_repo):
        """Create service instance with mocked dependencies."""
        return StateService(
            state_repo=mock_repo,
            transition_repo=MagicMock(),
            git_manager=MagicMock(),
            settings=MagicMock(),
        )

    def test_create_state_success(self, service, mock_repo):
        """Test successful state creation."""
        # Arrange
        mock_repo.create.return_value = True
        mock_repo.get_current.return_value = None

        # Act
        state = service.create_state("Test prompt")

        # Assert
        assert state.user_prompt == "Test prompt"
        assert state.state_number == 1
        mock_repo.create.assert_called_once()

    def test_create_state_validation_error(self, service):
        """Test state creation with invalid input."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            service.create_state("")
```

### Test Coverage Requirements
- **Unit Tests**: 100% coverage for business logic
- **Integration Tests**: Database operations, Git integration
- **Security Tests**: Input validation, rate limiting, authentication
- **Performance Tests**: Response times, memory usage, scalability

## Documentation Guidelines

### README Structure
- Project overview and purpose
- Installation and setup instructions
- Usage examples
- API documentation
- Contributing guidelines
- License information

### Code Documentation
- All public APIs must have docstrings
- Complex algorithms need inline comments
- TODO comments for future improvements
- FIXME comments for known issues

## Git and Version Control

### Branching Strategy
```bash
# Feature development
git checkout -b feature/add-state-validation

# Bug fixes
git checkout -b fix/state-transition-bug

# Releases
git checkout -b release/v1.2.0
```

### Commit Messages
Follow conventional commits:
```
feat(core): add state validation middleware
fix(repository): resolve race condition in SQLite
docs(readme): update installation instructions
test(security): add CWE-22 path traversal tests
refactor(services): extract common validation logic
```

### Versioning
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Database and Persistence

### Neo4j Schema
```
(:State {
  state_number: int,
  user_prompt: string,
  state_hash: string,
  created_at: datetime
})-[:TRANSITION_TO {
  transition_id: string,
  timestamp: datetime,
  prompt: string
}]->(:State)
```

### SQLite Schema
```sql
CREATE TABLE states (
    state_number INTEGER PRIMARY KEY,
    user_prompt TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transitions (
    transition_id TEXT PRIMARY KEY,
    from_state INTEGER,
    to_state INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_prompt TEXT,
    FOREIGN KEY (from_state) REFERENCES states(state_number),
    FOREIGN KEY (to_state) REFERENCES states(state_number)
);
```

### Migration Strategy
- Schema versioning with migration scripts
- Backward compatibility for data migration
- Rollback procedures for failed migrations
- Data integrity validation after migrations

## Codebase State Manager Tool Integration

### Operational Requirements

**MANDATORY WORKFLOW FOR ALL AGENTS:**

#### 1. Pre-Action State Check
**OBRIGATÓRIO**: ANTES de qualquer ação que modifique arquivos ou o estado do projeto, obtenha informação do estado atual usando:
```python
# Use the codebase-state-manager tool
current_state = await get_current_state_info_tool()
```

#### 2. Post-Action State Transition
**OBRIGATÓRIO**: Após completar TODAS as operações que alteraram arquivos ou o estado do projeto, como última ação, registre uma nova transição de estado com resumo da sessão:
```python
# Use the codebase-state-manager tool
await new_state_transition_tool(
    user_prompt="Summary of changes made: [detailed description of actions, impacts, decisions taken, problems solved, next steps]"
)
```

### When to Use State Transitions

**ALWAYS** create state transitions when:
- ✅ Modifying source code files
- ✅ Adding/removing files
- ✅ Changing configuration
- ✅ Updating dependencies
- ✅ Refactoring code structure
- ✅ Fixing bugs
- ✅ Adding features
- ✅ Updating documentation (if it affects functionality)

**NEVER** create state transitions for:
- ❌ Reading files for analysis
- ❌ Running tests (unless fixing test failures)
- ❌ Running linters/formatters (unless fixing issues)
- ❌ Purely informational queries

### State Transition Prompts

Use descriptive, comprehensive prompts that include:

```python
# Good examples:
await new_state_transition_tool(
    user_prompt="Implemented user authentication feature: added JWT token validation, created User model, updated API endpoints with auth middleware, added comprehensive tests covering edge cases, resolved race condition in concurrent logins"
)

await new_state_transition_tool(
    user_prompt="Fixed database connection leak: identified root cause in connection pooling, implemented proper cleanup in StateRepository, added connection health checks, updated error handling for network failures"
)

# Bad examples (too vague):
await new_state_transition_tool(user_prompt="Made some changes")
await new_state_transition_tool(user_prompt="Fixed bug")
```

### Error Handling with State Manager

```python
try:
    # Get current state before any changes
    current_state = await get_current_state_info_tool()

    # Perform operations that may modify files
    await modify_files()
    await run_tests()
    await update_dependencies()

    # Always register state transition on success
    await new_state_transition_tool(
        user_prompt="Successfully completed [operation]: [detailed summary]"
    )

except Exception as e:
    # Log error but still attempt state transition for failed operations
    await new_state_transition_tool(
        user_prompt="Failed [operation]: [error description] - partial changes may have been applied"
    )
    raise
```

### Integration with Development Workflow

```python
# Complete development workflow example
async def implement_feature(feature_description: str):
    # 1. Always check current state first
    current_state = await get_current_state_info_tool()

    # 2. Analyze and plan
    analysis = await analyze_requirements(feature_description)

    # 3. Implement changes
    await implement_code_changes(analysis)

    # 4. Run tests and quality checks
    await run_quality_checks()

    # 5. Always register state transition last
    await new_state_transition_tool(
        user_prompt=f"Implemented {feature_description}: {analysis.summary}, "
                   f"added {analysis.new_files} files, modified {analysis.changed_files} files, "
                   f"added {analysis.new_tests} tests, resolved {analysis.issues_fixed} issues"
    )
```

### State Manager Error Handling

If the codebase-state-manager tool is unavailable or fails:
1. Log the issue clearly
2. Continue with the primary task
3. Note in documentation that state transition was not recorded
4. Consider it a critical issue requiring manual state management

```python
try:
    await get_current_state_info_tool()
except ToolUnavailableError:
    logger.warning("Codebase state manager unavailable - proceeding without state tracking")
    # Continue with task but note the limitation
```

This integration ensures complete traceability of all codebase changes while maintaining development productivity.</content>
<parameter name="filePath">AGENTS.md