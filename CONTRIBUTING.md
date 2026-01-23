# Contributing to Codebase State Manager MCP Server

Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Docker (optional, for containerized development)
- uv (recommended) or poetry

### Development Setup

```bash
# Clone the repository
git clone https://github.com/anomalyco/codebase_state_manager_mcp.git
cd codebase_state_manager_mcp

# Install dependencies with uv (recommended)
./scripts/setup.sh

# Or with poetry
poetry install
```

## Development Workflow

### 1. Create a Feature Branch

```bash
# Start a new feature branch
git checkout -b feature/your-feature-name

# Or use git-flow
git-flow start-work feature/your-feature-name
```

### 2. Make Changes

Follow these guidelines when making changes:

- **Code Style**: Follow PEP 8 and use the project's configured formatters
- **Type Safety**: Ensure full type coverage; run `uv run mypy src/`
- **Testing**: Add tests for new functionality; run `uv run pytest`
- **Security**: Run security checks with `uv run bandit -r src/`

### 3. Run Pre-commit Hooks

Before committing, ensure all checks pass:

```bash
# Make the hook executable (first time only)
chmod +x .git/hooks/pre-commit

# Run manually
.git/hooks/pre-commit
```

This will run:
- Code formatting (black, isort)
- Type checking (mypy)
- Security analysis (bandit)
- Tests

### 4. Commit Changes

Follow conventional commits:

```bash
# Format: <type>(<scope>): <description>

# Examples:
git commit -m "feat(core): add new state transition validator"
git commit -m "fix(repository): resolve race condition in SQLite"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(security): add CWE-22 path traversal tests"
```

Types:
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or modifying tests
- `chore`: Maintenance tasks

### 5. Submit a Pull Request

1. Push your branch to GitHub
2. Create a Pull Request with a clear description
3. Ensure all CI checks pass
4. Request review from maintainers

## Testing

### Running Tests

```bash
# All tests
./scripts/run_tests.sh

# Unit tests only
./scripts/run_tests.sh unit

# Security tests only
./scripts/run_tests.sh security

# Integration tests only
./scripts/run_tests.sh integration

# With coverage
./scripts/run_tests.sh --coverage
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Place E2E tests in `tests/e2e/`
- Place security tests in `tests/security/`
- Place performance tests in `tests/performance/`

Follow existing test patterns and use pytest fixtures from `conftest.py`.

## Code Guidelines

### Architecture

This project follows Clean Architecture with these layers:

```
src/mcp_server/
├── tools/        # MCP tool definitions
├── services/     # Business logic (StateService, GitManager)
├── repositories/ # Data access (Neo4j, SQLite)
├── models/       # Data models (State, Transition)
└── utils/        # Utilities (validation, logging, metrics)
```

### Security

- Never commit secrets or credentials
- Sanitize all user inputs
- Use parameterized queries
- Follow OWASP guidelines

### Performance

- Aim for O(1) operations where possible
- Use connection pooling for databases
- Monitor with the built-in metrics system

## Documentation

### Updating Documentation

- Update README.md for user-facing changes
- Update API_REFERENCE.md for API changes
- Update CHANGELOG.md following Keep a Changelog format
- Add docstrings to all public functions and classes

### Docstring Format

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """Short description of the function.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        SomeError: When this error occurs
    """
```

## Release Process

### Version Bumping

This project uses Semantic Versioning:

- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes (backward compatible)

Update version in:
- `pyproject.toml`
- `CHANGELOG.md`

### Building for Release

```bash
# Build the package
python3 -m build

# Verify the build
twine check dist/*
```

## Contact

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Security: See SECURITY.md

## Code of Conduct

This project follows the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code.
