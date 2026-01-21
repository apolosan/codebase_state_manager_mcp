# Codebase State Manager - MCP Server

## Introduction

This MCP server helps any developer to easily manage the progress and evolution of its project by creating, updating and monitoring a state manager for the codebase. It provides sufficient context for a coding AI Agent (usually a LLM) to better understand where it was, where it is now and how is going the progress/development in the process.

After leaving a vibe coding session and coming back again, you usually need to store information to provide context for your agent in the next time. Generally, this information is stored in files or databases, with poor or no context at all. By using this MCP server, you don't need to worry about what you were doing or which phase/stage of the plan the agent was last time you were working on the project.

## How it works

This MCP takes the following information of any codebase:

    1. User prompt/request - All user prompts given for an AI Agent are saved in the codebase at every request
    2. `git branch --show-current` - Current branch name
    3. `git diff HEAD~3` - After the last changes

From this information, the tool generates a hash from it and put everything in a tuple: 1. State Tuple: <STATE_NUMBER, USER_PROMPT, BRANCH_NAME, GIT_DIFF_INFO, HASH>

Transitions are also stored in a tuple: 2. Transition Tuple: <ID/INDEX, CURRENT_STATE, NEXT_STATE, DATE_TIME>

## Tools Definition

**genesis()** - Initialize a state machine for the managed project and creates the state #0 (zero). Creates a branch called 'codebase-state-machine' copied from the current branch where the tool was called from. The new branch will be stored in a local dedicated volume in the docker container. If no git repository exists, initializes one in the container volume context only (keeping host unversioned). It MUST be the first tool to be called in the MCP server initialization. Validate if already initialized to prevent duplicate calls.

**new_state_transition(string prompt)** - Performs a transition from the user prompt/request, automatically using the current state as previous_state, to a newly created state. The transition is recorded with the provided prompt, and the current state always advances to the new one. The MCP server automatically manages all transitions. Generally, is performed **AFTER** the AI Agent completes a task for a given user prompt

**arbitrary_state_transition(number next_state)** - Performs an arbitrary state transition from the current state to a given next_state number. The transition (jump) is recorded. If the target state's USER_PROMPT is not defined or unclear, it is set to "Arbitrary transition" for consistency. Used when user explicitly requests state jumps in Opencode prompts.

**get_current_state_number()** - Returns only the number of the current managed state

**get_current_state_info()** - Returns information (tuple) of the current managed state. Provides the context needed for the AI Agent and should be called **BEFORE** submitting any prompt/request for it. In Opencode integration, use prompt engineering to ensure invocation before user requests.

**get_current_state_transitions()** - Returns all transitions (transition_id) for the current managed state

**get_state_info(number state)** - Returns all information (tuple) for a given state number

**get_state_transitions(number state)** - Returns all transitions (transition_id) for a given state number

**get_transition_info(number transition_id)** - Returns information (tuple) of a given transition

**search_states(string text)** - Returns all states (number of the state) which have the parameter text contained in their prompt (a context)

**track_transitions()** - Returns information (transition_id) of the last 5 transitions in sequence (if exists) of the current state

**total_states()** - Returns the total number of states managed by the state manager. It also helps to track the last number used for state numbering

## Rules

1. Define an universal counter for the current state machine - total_states()
2. Dockerize everything
3. Create copy and perform versioning (using git), if it wasn't yet, of the current project (by considering .gitignore) to a container volume
4. Transition database: id/index, current_state, next_state, date_time
5. A graph knowledge database (Neo4j) can store a state as a node and a transition as a relation
   5.1. If a graph knowledge cannot be used, a SQLite database can perform the task. It's not perfect, but possible
6. A transition can not be duplicated

## Dependencies

1. Docker + Git (can be downloaded during the container creation)
2. Neo4j - For graph knowledge database

## Opencode Integration
To ensure tools are invoked at appropriate times (BEFORE/AFTER user requests) when the MCP server is configured in Opencode:
- Use prompt engineering to instruct the agent explicitly (e.g., "Call get_current_state_info() before responding").
- Implement internal validations in tools (e.g., genesis checks for prior initialization; new_state_transition requires genesis).
- Rely on agent-driven decisions, as Opencode lacks forced hooks; simulate order via external scripts or custom commands.
- Test invocation order through E2E simulations in Opencode sessions.

## Crazy Ideas

1. Store the state transition in a blockchain