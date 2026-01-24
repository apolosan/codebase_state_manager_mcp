# Codebase State Manager MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-440%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-90%25-green.svg)]()
[![mypy](https://img.shields.io/badge/mypy-passing-green.svg)]()
[![Bandit](https://img.shields.io/badge/bandit-clean-green.svg)]()
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)]()
[![Status: WIP](https://img.shields.io/badge/status-WIP-yellow.svg)]()

A sophisticated Model Context Protocol (MCP) server for managing codebase states with version control, graph database tracking, and containerized execution environments.

**⚠️ WORK IN PROGRESS (WIP) - This project is actively under development. Features may change, APIs may evolve, and breaking changes are expected during the development phase.**

## ⚠️ Important Notice

**USE AT YOUR OWN RISK**

This software is provided "as-is" without any warranties or guarantees. Users assume full responsibility for:

- Any data loss or corruption
- Security vulnerabilities introduced through usage
- Compliance with applicable laws and regulations
- Proper backup and recovery procedures
- Testing in isolated environments before production use

The developers are not liable for any damages, losses, or issues arising from the use of this software.

## 🚀 Features

### Core Capabilities
- **State Machine Management**: Track codebase evolution through numbered states
- **Git Integration**: Capture diffs, branches, and commit history
- **Graph Database Storage**: Neo4j for relationship-based state tracking
- **SQLite Fallback**: Relational database support when Neo4j is unavailable
- **Docker Containerization**: Isolated execution environments for git operations

### Advanced Features
- **State Transitions**: Linear and arbitrary transitions between codebase states
- **Content Hashing**: SHA256 hashing for state integrity verification
- **Search & Query**: Full-text search across state prompts and diffs
- **Performance Metrics**: Detailed timing and operation statistics
- **Structured Logging**: JSON-formatted logs with session context
- **Security Layers**: Input validation, rate limiting, and audit logging

## 🏗️ Architecture

The system follows Clean Architecture principles with clear separation of concerns:

```
MCP Client → Tools Layer → Services Layer → Repositories Layer → Database
```

### Key Components
- **MCP Tools Layer**: Protocol interface and tool definitions
- **Services Layer**: Business logic (StateService, GitManager)
- **Repositories Layer**: Data access abstraction (Neo4j/SQLite)
- **Utilities**: Security, logging, metrics, and validation modules

For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Git
- Neo4j (optional, for graph database features)

### Installation
```bash
# Clone the repository
git clone https://github.com/apolosan/codebase_state_manager_mcp.git
cd codebase_state_manager_mcp

# Setup environment (uses uv if available)
./scripts/setup.sh

# Verify installation with tests
./scripts/run_tests.sh
```

### Using uv (Recommended)
```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup with uv
./scripts/setup.sh --sync

# Run development server
./scripts/dev.sh
```

## 🛠️ Usage

### Starting the MCP Server
```bash
# Using the launcher script
python run_mcp_server.py

# Or directly via module
python -m src.mcp_server
```

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build

# Run test suite in Docker
docker-compose -f docker-compose.test.yml up --build
```

### Available MCP Tools

#### State Management
- `genesis()` - Create initial state #0
- `new_state_transition(prompt)` - Create next sequential state
- `arbitrary_state_transition(target_state, prompt)` - Jump to any existing state
- `get_current_state_info()` - Get details of current state
- `get_state_info(state_number)` - Get details of specific state
- `total_states()` - Count total states
- `search_states(text)` - Search across state prompts

#### Transition Tracking
- `get_state_transitions(state_number)` - Get transitions from/to a state
- `get_transition_info(transition_id)` - Get transition details
- `track_transitions()` - Monitor recent transitions
- `get_current_state_transitions()` - Get transitions for current state

## 🔧 Configuration

### Environment Variables
Create a `.env` file based on `.env.example`:

```bash
# Database Configuration
DB_MODE=neo4j  # or sqlite
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Docker Settings
DOCKER_VOLUME_NAME=codebase_volume
VOLUME_PATH=/path/to/volume

# Security Settings
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### Database Modes

#### Neo4j Mode (Recommended)
```yaml
# docker-compose.yml
neo4j:
  image: neo4j:5.24
  environment:
    NEO4J_AUTH: neo4j/password
  ports:
    - "7474:7474"  # Browser UI
    - "7687:7687"  # Bolt protocol
```

#### SQLite Mode (Fallback)
Automatically falls back to SQLite when Neo4j is unavailable. Data is stored in `data/state_manager.db`.

## 📊 Testing

### Test Suite
```bash
# Run all tests
./scripts/run_tests.sh

# Specific test categories
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh security
./scripts/run_tests.sh e2e

# With coverage report
./scripts/run_tests.sh --coverage
```

### Test Statistics
- **440 Total Tests**: 100% passing
- **90% Code Coverage**: Comprehensive test suite
- **Security Tests**: Bandit, audit logging, rate limiting
- **Performance Tests**: Stress testing and metrics validation
- **Integration Tests**: Docker, Neo4j, SQLite integration

## 🔒 Security

### Built-in Security Features
- **Input Validation**: Sanitization of all user inputs
- **Rate Limiting**: Token bucket algorithm per client
- **Audit Logging**: Comprehensive operation tracking
- **Content Hashing**: SHA256 verification of state integrity
- **Container Isolation**: Docker-based git operations
- **No Hardcoded Secrets**: Environment-based configuration only

### Security Testing
```bash
# Run security tests
./scripts/run_tests.sh security

# Bandit security scan
uv run bandit -r src/

# Custom security validation
python -m pytest tests/security/ -v
```

## 📈 Performance

### Monitoring & Metrics
- **PerformanceMonitor**: Tracks state transitions, DB queries, git operations
- **MetricsCollector**: Aggregates counters and timing statistics
- **@timed_operation**: Decorator for automatic performance profiling
- **Structured Logging**: JSON output for easy parsing and analysis

### Optimization Features
- **Connection Pooling**: Efficient database connection management
- **Lazy Loading**: On-demand resource initialization
- **Caching**: Frequently accessed state information
- **Async Operations**: Non-blocking I/O where applicable

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Development Setup
```bash
# Install development dependencies
./scripts/setup.sh

# Activate pre-commit hooks
chmod +x .git/hooks/pre-commit
.git/hooks/pre-commit

# Run development server
./scripts/dev.sh
```

### Code Quality
- **Type Checking**: mypy with strict settings
- **Code Formatting**: Black and isort
- **Linting**: Custom pre-commit hooks
- **Documentation**: Comprehensive docstrings and API references

### Testing Guidelines
1. Write tests for all new functionality
2. Maintain 90%+ code coverage
3. Include security tests for sensitive operations
4. Add integration tests for database interactions
5. Include performance tests for critical paths

For comprehensive agent guidelines, see [AGENTS.md](AGENTS.md).

## 📚 Documentation

### Key Documents
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design decisions
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines and processes
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [AGENTS.md](AGENTS.md) - Agent guidelines and operational requirements
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [SETUP.md](SETUP.md) - Detailed setup instructions

### Code Documentation
- Comprehensive docstrings following Google style
- Type hints for all function signatures
- Example usage in docstrings
- Error handling documentation

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer (Reiterated)

This software is experimental and should be used with extreme caution. Always:

1. **Backup your data** before use
2. **Test in isolated environments** first
3. **Monitor system resources** during operation
4. **Review security configurations** regularly
5. **Assume responsibility** for all usage consequences

The developers provide no warranties and accept no liability for any issues arising from the use of this software.

**Note:** This is a Work in Progress (WIP) project. The software is in active development and may undergo significant changes, including breaking API modifications, feature additions, and architectural improvements. Users should expect ongoing evolution and should not consider this a stable production-ready solution at this stage.