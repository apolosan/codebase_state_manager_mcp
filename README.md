# Codebase State Manager MCP

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-FastMCP-6f42c1.svg)](https://modelcontextprotocol.io/)
[![Storage](https://img.shields.io/badge/storage-Neo4j%20%7C%20SQLite-0a7b83.svg)]()
[![Built for](https://img.shields.io/badge/built%20for-AI%20coding%20agents-8a2be2.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)]()

**Persistent project state for AI coding agents.**

Codebase State Manager MCP gives any MCP-capable coding agent a durable memory of your project. Instead of retrying the same fix with slightly different prompts, the agent can query numbered states, transitions, Git-aware change summaries, compact SCC-E (State Compression Code — Embedding) context, rewards, and repair metadata before it acts.

If an agent keeps failing to solve the same bug, the missing ingredient is often not a better prompt. It is reliable state. This server turns your codebase history into a queryable system the model can inspect, compare, and reuse across sessions.

## Why developers using AI agents care

- You stop re-explaining the repo every time the context window resets.
- You give each new agent session the same project memory, even after model swaps or cold starts.
- You capture what changed, why it changed, and which transition actually moved the project forward.
- You keep stubborn recurring issues from turning into endless prompt archaeology.
- You choose the storage model that fits your workflow: managed Neo4j, external Neo4j, or SQLite.

## What the project stores

Every state can persist:

- the prompt that motivated the change;
- branch information;
- Git-aware change information (`git_diff_info`);
- file-hash snapshots or deltas;
- SCC-E (State Compression Code — Embedding) compact context (`llm_context`, `compression_version`, `compacted_at`).

Every transition can persist:

- source state;
- destination state;
- user prompt;
- timestamp;
- optional reward.

That gives your agent something chat history alone cannot provide: project-scoped memory that survives beyond a single conversation.

## What SCC and SCC-E mean in this project

In the language of this project, **SCC** means **State Compression Code**. It is the umbrella idea of compressing verbose state data into a smaller, model-friendly representation.

**SCC-E** means **State Compression Code — Embedding**. This is the compact format currently implemented in `src/mcp_server/services/scc_codec.py` and stored in each state through `llm_context`, `compression_version`, and `compacted_at`.

In practice, SCC-E takes the noisy parts of state history — changed paths, diff metadata, and file hashes — and rewrites them into a compact JSON payload that an agent can query cheaply. The codec uses a shared path vocabulary, short action markers, and compact hash encoding so the model sees the structure of a change without paying the full token cost of replaying raw diffs every time.

The **SCC** term also appears in the earlier idea-refinement documents as the broader compression concept and as a simpler baseline that mainly replaced paths with numeric IDs. The current codebase went further and implemented **SCC-E** as the LLM-facing representation, because the project needs compact state context that is useful to agents, not just smaller storage.

## How it helps with stubborn recurring issues

When a fix keeps bouncing between “almost correct” and “still broken,” Codebase State Manager gives the next repair round grounded context:

1. the exact prompt trail that led to the current state;
2. change evidence tied to the codebase, not just the chat thread;
3. compact LLM-oriented summaries the agent can query quickly;
4. rewardable transitions that help surface successful paths.

In practice, this changes the workflow from “try again with a new prompt” to “inspect what happened, reuse what worked, and correct what did not.” That is the difference between an agent guessing again and an agent operating with memory.

## Who it is for

This project is built for:

- developers shipping with MCP-capable coding agents;
- teams that switch between different models or agent runtimes on the same repo;
- maintainers who want an auditable trail of AI-assisted changes;
- projects where one bug or broken refactor keeps returning despite repeated instructions;
- local-first workflows that need inspectable infrastructure instead of black-box memory.

## When it becomes valuable

You will feel the value fastest when:

- an agent loses context after a long session;
- a bug survives several repair attempts;
- you want to compare multiple agent-generated approaches;
- you need a compact summary instead of replaying an entire chat;
- you want to resume work later without trusting the model to remember correctly.

## Why this is different from plain chat history

- Chat history is thread-bound. Codebase State Manager is project-bound.
- A prompt transcript tells you what was said. A state machine tells you what changed.
- A model memory is agent-specific. MCP queries are agent-agnostic.
- Repeated “fix this again” loops hide successful steps. Rewarded transitions keep them visible.
- Long context windows still decay. Persisted compact state stays queryable.

## Core capabilities

| Capability                                                 | Why it matters for agent-driven development                                  |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Numbered states and transitions                            | Creates a durable, queryable history for the codebase                        |
| SCC-E (State Compression Code — Embedding) compact context | Feeds smaller, LLM-oriented state summaries back to the agent                |
| `raw`, `compact`, and `both` state representations         | Lets the client choose the right detail level per tool call                  |
| Rewarded transitions                                       | Highlights useful repair paths and successful changes                        |
| Managed Neo4j bootstrap                                    | Removes setup friction for graph-backed persistence                          |
| SQLite support                                             | Keeps the project simple and local when Docker or Neo4j are unnecessary      |
| Workspace snapshot recovery                                | Rebuilds or verifies the managed working copy when drift appears             |
| Consistency check and auto-repair tools                    | Helps agents recover from runtime state problems instead of compounding them |
| Logical parity across Neo4j and SQLite                     | Preserves the same domain contract across both backends                      |

## Built for today’s agents, aimed at reinforcement learning

The current product direction is bigger than state tracking alone. The roadmap is actively converging on **reinforcement-learning support for coding agents**: richer state-action history, better reward signals, and stronger feedback loops that help agent-driven development improve over time instead of restarting from scratch on every session.

That direction is a strong fit for this project because the hard part of learning from code-generation workflows is not only scoring outcomes. It is preserving the **state**, the **action trail**, and the **reward context** in a form that can be queried, audited, and reused. Codebase State Manager is being shaped to become that memory and feedback layer.

**Important:** full reinforcement learning support is **not available in version `0.2.1`**.

What the current version already gives you:

- durable state history for agent-driven work;
- compact SCC-E context for low-cost recall;
- rewarded transitions as an early feedback primitive;
- persistent storage that survives chat resets and agent swaps.

What is still ahead of the current release:

- end-to-end reinforcement learning workflows;
- automated training or policy-optimization loops;
- production-ready RL orchestration on top of the MCP server.

That means you can adopt the project now for immediate reliability gains, while aligning yourself with a roadmap aimed at agents that do more than generate code — agents that can eventually learn from repeated outcomes.

## Storage modes

| Mode                    | Best fit                                      | Persistent location            |
| ----------------------- | --------------------------------------------- | ------------------------------ |
| Managed Neo4j (default) | You want graph persistence with minimal setup | `./.data/neo4j/`               |
| SQLite                  | You want the simplest local setup             | `./data/state_manager.db`      |
| External Neo4j          | Your infrastructure already runs Neo4j        | Your configured Neo4j instance |

Managed Neo4j mode automatically creates or reuses a **project-scoped** Neo4j container. MCP client configuration does not need Neo4j credentials in this mode.

When `VOLUME_PATH` is not set, the managed workspace snapshot defaults to:

```text
/opt/codebase-state-manager/volumes/<current-project-dir-name>
```

That keeps the managed snapshot outside the project tree by default.

## Quick start

### Prerequisites

Required:

- Python **3.10+**
- `uv`
- Git

Required only for managed Neo4j mode:

- Docker daemon running locally

### Install

```bash
git clone <repository-url>
cd codebase_state_manager_mcp
./scripts/setup.sh
```

Alternative direct install with uv:

```bash
uv sync --extra dev
```

### Start the server

Recommended launcher:

```bash
python run_mcp_server.py
```

Alternative module entrypoint:

```bash
python -m src.mcp_server
```

Legacy compatibility launcher:

```bash
python init_neo4j_and_mcp.py
```

Use `run_mcp_server.py` for all new integrations.

## Minimal MCP client configuration

Recommended configuration for managed Neo4j mode:

```json
{
  "mcp": {
    "codebase-state-manager": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--project",
        "/absolute/path/to/codebase_state_manager_mcp",
        "python",
        "run_mcp_server.py"
      ],
      "enabled": true
    }
  }
}
```

For SQLite mode, set:

```json
{
  "DB_MODE": "sqlite"
}
```

For external Neo4j mode, set:

```json
{
  "DB_MODE": "neo4j",
  "NEO4J_BOOTSTRAP_MODE": "external",
  "NEO4J_URI": "bolt://localhost:7687",
  "NEO4J_USER": "neo4j",
  "NEO4J_PASSWORD": "your_password"
}
```

See [SETUP.md](SETUP.md) for the full installation, environment, and troubleshooting guide.

## High-value tools for agent workflows

The FastMCP server currently exposes **25** tools. Most agent-driven workflows start with the tools below.

### Initialize and capture state

- `genesis_tool`
- `start_genesis_tool`
- `get_genesis_status_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`

### Inspect and search history

- `get_current_state_info_tool`
- `get_state_info_tool`
- `get_current_state_number_tool`
- `total_states_tool`
- `search_states_tool`
- `get_state_transitions_tool`
- `get_current_state_transitions_tool`
- `get_transition_info_tool`
- `track_transitions_tool`

### Query compact LLM context

- `get_current_state_compact_context_tool`
- `get_compact_states_tool`

### Reuse successful paths

- `get_rewarded_transitions_tool`
- `set_transition_reward_tool`

### Recover and repair runtime state

- `fix_volume_path_tool`
- `start_fix_volume_path_tool`
- `get_fix_volume_path_status_tool`
- `get_fix_volume_path_result_tool`
- `check_consistency_tool`
- `repair_consistency_tool`

## State representations

Tools that return a `State` support:

- `raw` — full legacy payload
- `compact` — only compact SCC-E (State Compression Code — Embedding) view
- `both` — both representations together

Supported today on:

- `genesis_tool`
- `get_genesis_result_tool`
- `new_state_transition_tool`
- `arbitrary_state_transition_tool`
- `get_current_state_info_tool`
- `get_state_info_tool`

## Quality and architecture signals

The repository is designed to earn trust from developers who work with agents daily:

- layered runtime structure under `src/mcp_server/{tools,services,repositories,models,utils}`;
- dual-backend persistence with parity expectations for `State` and `Transition` fields;
- typed Python code with mypy configuration;
- security scanning with Bandit;
- test coverage across unit, integration, end-to-end, security, performance, and stress suites.

If you want the exact implementation details, read:

- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture and storage mapping
- [SETUP.md](SETUP.md) — installation, environment variables, troubleshooting
- [QUICKSTART.md](QUICKSTART.md) — minimal setup and client configuration
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributor workflow and validation checklist
- [CHANGELOG.md](CHANGELOG.md) — release history and release intent
- [AGENTS.md](AGENTS.md) — repository instructions for coding agents

## What adoption looks like

A typical workflow looks like this:

1. Initialize the project once with `genesis_tool`.
2. Let your agent create meaningful checkpoints with `new_state_transition_tool`.
3. When a fix stalls, query `search_states_tool`, `get_current_state_info_tool`, `get_compact_states_tool`, and `get_rewarded_transitions_tool` before prompting blindly again.
4. If the managed workspace or runtime drifts, use `check_consistency_tool`, `repair_consistency_tool`, or `fix_volume_path_tool`.
5. Resume from real project state instead of trusting the model to remember everything.

That workflow makes the MCP server more than a logger. It becomes a memory layer for code generation, debugging, and recovery.

## License

MIT. See [LICENSE](LICENSE).
