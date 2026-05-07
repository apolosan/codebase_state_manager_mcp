# Contributing

Thank you for contributing to **Codebase State Manager MCP Server**.

This document reflects the current project workflow for version **0.2.1**.

---

## 1. Prerequisites

Required:
- Python 3.10+
- `uv`
- Git

Optional but recommended:
- Docker, if you need to exercise managed Neo4j mode locally

Install dependencies:

```bash
./scripts/setup.sh
```

Or directly:

```bash
uv sync --extra dev
```

---

## 2. Development Commands

### Start the server

```bash
python run_mcp_server.py
```

### Development runner

```bash
./scripts/dev.sh
```

### Run tests

```bash
python -m pytest tests -q
```

Helper script:

```bash
./scripts/run_tests.sh
```

### Static validation

```bash
uv run mypy src/
uv run bandit -r src/ -q
```

### Formatting

```bash
uv run black src/ tests/
uv run isort src/ tests/
```

---

## 3. Repository Workflow

A normal contributor workflow is:

1. create a branch;
2. implement the change;
3. add or update tests;
4. run validation locally;
5. update documentation when behavior changes;
6. open a pull request.

Suggested commit style:

```text
feat(scope): description
fix(scope): description
docs(scope): description
test(scope): description
refactor(scope): description
chore(scope): description
```

---

## 4. Contribution Rules

### Keep behavior and docs aligned
If you change:
- tool names,
- startup behavior,
- configuration,
- persistence model,
- state/transition payloads,
- Neo4j or SQLite behavior,

then update the relevant docs:
- `README.md`
- `QUICKSTART.md`
- `SETUP.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`

### Preserve backend parity
If you add or change persisted domain fields, update **both** backends unless the difference is intentionally architecture-specific.

Current parity expectations:
- all `State` domain fields must be available in SQLite and Neo4j;
- all `Transition` domain fields must be available in SQLite and Neo4j;
- mapping differences are acceptable only when they do not change domain behavior.

### Preserve the launcher contract
The canonical launcher is:
- `run_mcp_server.py`

The legacy alias:
- `init_neo4j_and_mcp.py`

may be kept for backward compatibility, but new docs and examples must use the canonical launcher.

### Preserve state representation compatibility
Tools that return a `State` must keep supporting:
- `raw`
- `compact`
- `both`

### Preserve SCC-E behavior
Changes to SCC-E must maintain:
- valid `llm_context`
- backward-safe vocabulary evolution
- stable compact preview generation

---

## 5. Testing Expectations

At minimum, before opening a PR, run:

```bash
python -m pytest tests -q
uv run mypy src/
uv run bandit -r src/ -q
```

If your change affects only a small area, run the targeted tests first, then the full suite.

When touching:
- startup/configuration → include unit coverage for config and launcher behavior
- SQLite/Neo4j persistence → include repository or integration coverage
- tools → include tool-level tests
- state transitions or SCC-E → include service-level tests

---

## 6. Architecture Guidelines

The codebase is organized under:

```text
src/mcp_server/
├── tools/
├── services/
├── repositories/
├── models/
└── utils/
```

Guidelines:
- keep tool wrappers thin;
- keep business logic in services;
- keep persistence rules in repositories;
- keep domain payload shape consistent across backends;
- prefer small, explicit changes over hidden behavior.

---

## 7. Documentation Style

Use clear technical language and avoid stale claims.

Good examples:
- exact command lines;
- exact tool names;
- exact environment variables;
- exact validation results when they are known.

Avoid:
- claiming checks passed when they were not run;
- documenting old launchers as recommended;
- describing tools that are not actually exposed by `FastMCP`.

---

## 8. Release and Versioning

The project uses semantic versioning.

When preparing a release:
- update `pyproject.toml`
- update `CHANGELOG.md`
- update any version references in documentation

Current canonical version file:
- `pyproject.toml`

---

## 9. Final Checklist

Before considering a change ready:

- [ ] tests pass
- [ ] mypy passes
- [ ] bandit passes
- [ ] docs updated if behavior changed
- [ ] SQLite/Neo4j parity checked if persistence changed
- [ ] launcher/docs use `run_mcp_server.py`
- [ ] changelog updated when appropriate
