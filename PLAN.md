# Comprehensive Development Plan for Codebase State Manager MCP Server

## Executive Summary
This plan outlines the complete development roadmap for the Codebase State Manager MCP Server, based on the specification in `specification_corrected.md` and the recommended tech stack in `TECH_STACK.md`. The project implements a Python-based MCP server for tracking codebase states via Git operations, hashing, and graph storage in Neo4j (with SQLite fallback), all Dockerized. Key goals: Unbounded state management, secure API tools, 100% test coverage, and adherence to SOLID/Security principles.

Total estimated timeline: 8-12 weeks for MVP (assuming 1-2 developers, 40 hrs/week). Phases are sequential but allow parallel work (e.g., testing/DB impl). Risks mitigated via iterative validation with Spotlight and pytest. Research leveraged arXiv (e.g., hindsight logging for state replay, API state mgmt patterns), GitHub (GitPython+Neo4j examples in repo mgmt tools), and design patterns (Repository for DB access, Event Sourcing for transitions).

Budget/Resources: Python 3.10+, Git, Docker/Compose, Neo4j Community Edition (free), pytest/bandit (free). Dev env: VS Code, GitHub for collab.

## Project Scope & Assumptions
- **In Scope**: Core tools (genesis, new_state_transition, etc.), DB schema, Docker setup, security/logging, full testing, docs.
- **Out of Scope**: UI (add later if needed via shadcn), Blockchain integration (optional POC), Production CI/CD beyond basics.
- **Assumptions**: New repo; Access to Docker/Neo4j; No existing codebase conflicts. Unbounded states: Neo4j scales to 1M+ nodes (per docs).
- **Success Metrics**: 100% test coverage, no vulnerabilities (bandit scan), query perf <100ms, successful E2E Docker flows.

## Architecture Overview
Adopt a layered architecture: API Layer (MCP tools as functions/endpoints), Service Layer (business logic: hashing, git ops), Repository Layer (DB abstraction for Neo4j/SQLite), Infrastructure (Docker volumes). Use Event Sourcing for immutable transitions; Dependency Injection for testability. No current architecture (new project), so establish Repository Pattern (from design-patterns) for DB ops, ensuring low coupling.

High-Level Diagram (ASCII):
```
[Client/AI Agent] --> [MCP API Tools (e.g., genesis())]
                     |
                     v
[Service Layer] (GitPython, Hashing, State Logic)
                     |
                     v
[Repository Layer] (Neo4j Cypher/Driver, SQLAlchemy for SQLite)
                     |
                     v
[Persistence] (Neo4j Graph or SQLite DB)
                     |
                     v
[Docker Container] (Volumes for Git Repo, Isolated Env)
```

## Phase 1: Project Setup & Environment (Week 1)
- **Objectives**: Establish dev env, install deps, init repo.
- **Sub-Tasks**:
  1. Init Git repo: `git init`, add .gitignore (Python/Docker), commit initial structure (src/, tests/, docker/).
  2. Setup Python env: Virtualenv/Poetry; Install core deps (`GitPython==3.1.40`, `neo4j==5.24.0`, `sqlalchemy==2.0.35`, `python-dotenv` for env vars).
  3. Dev deps: `pytest==8.3.3`, `pytest-cov`, `bandit==1.7.9`, `docker==7.1.0`.
  4. Config: .env for DB creds (NEO4J_URI, NEO4J_USER, etc.); Config class for modes (neo4j/sqlite).
  5. Project structure: src/mcp_server/ (tools.py, services/, repositories/, models.py).
- **Dependencies**: None (bootstrap).
- **Risks/Mitigations**: Dep conflicts - use Poetry lockfile. Validate with `pip check`.
- **Validation**: Run `pytest --collect-only` (empty pass), bandit scan (clean).
- **Milestone**: Working env; Initial commit.

## Phase 2: Database Schema & Models (Weeks 1-2)
- **Objectives**: Implement state/transition storage.
- **Sub-Tasks**:
  1. Define models: State (id: int, prompt: str, branch: str, diff: str, hash: str); Transition (id: uuid, from_state: int, to_state: int, timestamp: datetime).
  2. Neo4j Impl: Use driver to create schema (constraints on hash uniqueness); Cypher funcs for CREATE/MATCH (e.g., `MERGE (s:State {hash: $hash})` to prevent dups).
  3. SQLite Fallback: SQLAlchemy models; Tables with UNIQUE on transition hash; Migration script (Alembic).
  4. Abstraction: Repository pattern - `class StateRepo(ABC)` with methods like `create_state()`, `get_state_info(state_num)`.
  5. Toggle: Env var DB_MODE=neo4j/sqlite; Fallback logic in repo.
- **Dependencies**: Phase 1 deps.
- **Interferences**: None (isolated).
- **Research Insights**: arXiv (2006.07357) on hindsight logging - inspire event replay for `track_transitions()`. GitHub: Similar Git+DB in `neo4j-contrib/git-connector` examples.
- **Risks**: Graph perf for unbounded states - Index on STATE_NUMBER/HASH; Test with 10k inserts.
- **Validation**: Unit tests for create/get (mock driver); Coverage >90%; Spotlight for query traces (<50ms).
- **Milestone**: DB ops functional; Schema scripts committed.

## Phase 3: Core Tools Implementation (Weeks 2-4)
- **Objectives**: Build MCP functions per spec, with invocation order guarantees.
- **Sub-Tasks** (Apply SOLID: Single resp per tool):
  1. Hashing Utils: `def generate_state_hash(prompt, branch, diff):` using hashlib.sha256.
  2. Git Utils: `GitManager` class - `get_branch()`, `get_diff(commits=3)`, `clone_to_volume(project_path, volume_name)`.
  3. Genesis: Init state #0 (empty prompt/diff), create 'codebase-state-machine' branch in Docker vol, setup DB counter. If no local git repo exists, run `git init` only in Docker volume after copying files. Add validation: Prevent re-init if already called.
  4. New State Transition: Input prompt (previous_state auto-selected as current); Gen new num (total_states()+1), capture git info, hash, create state/transition, enforce no dup (hash check). Always set new state as current state. Add validation: Require genesis called first. Architecture designed for future extensibility to user-controlled transitions if needed.
  5. Arbitrary State Transition: Auto-use current as from_state, input next_state, validate exists, if target state's prompt empty/unset, set to "Arbitrary transition", create edge, no dup ID. Add validation: Require genesis.
  6. Getters: `get_current_state_number()` (query latest), `get_current_state_info()` (tuple return), `search_states(text)` (Cypher full-text), `track_transitions()` (limit 5 edges).
  7. Others: `total_states()` (COUNT nodes), `get_transition_info(id)`.
  8. API Layer: If RPC, use FastAPI for endpoints; Else, functions exposed via MCP protocol. Include clear error messages for order violations (e.g., "Call genesis first").
- **Dependencies**: Phases 1-2.
- **Interferences**: Git ops may conflict with host repo - Use isolated clones.
- **Research**: arXiv (2211.10291) on knowledge mgmt - Use for unbounded state querying. Design-patterns: Consistent Core for DB consistency.
- **Security**: Sanitize inputs (bleach for prompts), param queries, rate limit tools (e.g., 10/min via decorator).
- **Risks**: Git vol access - Handle permissions in Docker. Dup transitions - UUID+hash validation. Agent may ignore order - Mitigate with validations and prompt guidance.
- **Validation**: Integration tests (e.g., genesis → transition → get_info); pytest fixtures for DB/Git mocks; Test validations (e.g., fail without genesis).
- **Milestone**: All tools functional; E2E flow (genesis to track_transitions); Order validations working.

## Phase 4: Docker Integration & Containerization (Weeks 4-5)
- **Objectives**: Dockerize per spec.
- **Sub-Tasks**:
  1. Dockerfile: FROM python:3.10-slim; Install Git, copy code, expose ports if API.
  2. Docker Compose: Services - app, neo4j (official image), volumes for git repos (.gitignore filtered via git archive).
  3. Volume Mgmt: In genesis, `docker volume create project-vol`, copy repo excluding gitignore.
  4. Runtime: Tools run in container; Persist DB/vols externally.
  5. Build/Test: `docker build -t mcp-server .`; Multi-stage for slim prod image.
- **Dependencies**: Phase 3.
- **Interferences**: Host-Docker file sync - Use volumes/bind mounts.
- **Research**: GitHub patterns from `docker-git` repos - Clone in container via GitPython.
- **Risks**: Vol persistence - Backup scripts; Large diffs - Compress storage.
- **Validation**: E2E Docker test (desktop-commander: docker-compose up, run genesis); Spotlight traces for container perf.
- **Milestone**: Full Dockerized app; Compose yaml committed.

## Phase 5: Security, Logging & Best Practices (Week 5)
- **Objectives**: Secure & robust.
- **Sub-Tasks**:
  1. Auth: JWT/API keys for tools (FastAPI deps).
  2. Validation: Pydantic for inputs; Anti-injection via params.
  3. Rate Limit: slowapi middleware.
  4. Logging: structlog for transitions; Audit logs in DB.
  5. Secrets: Docker secrets/env; No commits.
  6. Lint/Sec: Black/isort, mypy (types), bandit scans.
  7. Principles: DI (inject repo to services), DRY (utils module), KISS (simple tuples).
- **Dependencies**: Phase 4.
- **Interferences**: Logging overhead - Async handlers.
- **Research**: arXiv (2510.03610) on secure MCP - RPC safeguards.
- **Risks**: Injection in prompts - Sanitize non-executables.
- **Validation**: Security tests (malicious inputs, CWE-78/22); Bandit clean.
- **Milestone**: Secure, lint-free code.

## Phase 6: Testing Suite (Weeks 6-7)
- **Objectives**: Comprehensive coverage, including invocation order guarantees.
- **Sub-Tasks**:
  1. Unit: Mock Git/DB, test hashing/transitions (edge: dup attempts fail); Validate internal checks (e.g., genesis prevents re-init).
  2. Integration: Real Neo4j/SQLite, git clones; Flows (genesis to search); Test validations (e.g., new_state_transition fails without genesis).
  3. E2E: Docker full stack, agent-browser sim calls; Unbounded stress (1000 states); Simulate Opencode integration by testing prompt-driven order (e.g., mock agent calls get_current_state_info before responses, new_state_transition after).
  4. Security: Fuzz prompts, auth bypass attempts.
  5. Coverage: pytest-cov >=100%; No any/unknown (mypy strict).
  6. Knip: Clean unused (though Python-focused, adapt for deps).
- **Dependencies**: All prior.
- **Interferences**: Test isolation - Fixtures teardown.
- **Research**: arXiv (1009.3713) on test synthesis - Automate E2E seqs.
- **Risks**: Flaky git tests - Use temp dirs; Order simulations may not reflect real agent behavior.
- **Validation**: Run full suite; Spotlight for runtime errors/traces; Build: python setup.py build (no npm, adapt to pyinstaller); Verify order via logs in E2E tests.
- **Milestone**: 100% coverage; All warnings fixed; Invocation order validated in sims.

## Phase 7: Performance Optimization & Monitoring (Week 7)
- **Objectives**: Efficient for large states.
- **Sub-Tasks**:
  1. Profile: cProfile for hotspots (git diff large repos).
  2. Opt: Neo4j indexes, batch queries; O(1) hash checks.
  3. Monitoring: Integrate Spotlight for traces/logs; Prometheus for metrics.
  4. Scale: Test 10k states (Neo4j sharding if needed).
- **Dependencies**: Phase 6.
- **Interferences**: Perf vs safety - Balance with locks for concurrent transitions.
- **Research**: arXiv (2303.15068) on DQSOps - Quality scoring for state data.
- **Risks**: N+1 queries - Use Cypher paths.
- **Validation**: Benchmarks (<100ms/query); Spotlight no bottlenecks.
- **Milestone**: Optimized MVP.

## Phase 8: Documentation & Deployment (Weeks 8-9)
- **Objectives**: Usable & deployable.
- **Sub-Tasks**:
  1. Docs: README (setup, tools), API (Sphinx), Diagrams (PlantUML for arch).
  2. Changelog: Version 0.1.0.
  3. CI/CD: GitHub Actions (tests, build Docker on push).
  4. Deploy: Docker Hub push; Optional: Heroku/AWS for hosted.
- **Dependencies**: Phase 7.
- **Interferences**: Doc maintenance - Markdown generation.
- **Research**: Design-patterns for docs (no code impact).
- **Risks**: Incomplete docs - Review checklist.
- **Validation**: Build docs; CI green.
- **Milestone**: Tagged release; Deployed container.

## Phase 9: Review & Iteration (Week 10+)
- **Objectives**: Feedback loop.
- **Sub-Tasks**: Code review (zen codereview), run full tests/Spotlight, fix issues (max 3 refactors per workflow). If fail, doc & request human review.
- **Risks**: Scope creep - Stick to spec.
- **Milestone**: Production-ready; Monitor initial use.

## Git Flow & Registration
- Init: git-flow init; Start feature branches per phase (e.g., feature/db-schema).
- Memory: Register phases/decisions in neo4j-memory (arch/decisions), memory (risks/next steps) - Alternated, connected to TechStackResearch.
- Monitoring: Weekly Spotlight reviews.

*Sources: arXiv (state logging, API synthesis); GitHub (GitPython patterns); Design-patterns (Repository/Event Sourcing). Total Effort: 320-480 hrs.*