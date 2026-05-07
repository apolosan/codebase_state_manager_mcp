"""Integration tests for the Neo4j repositories.

These tests use the managed project-scoped Neo4j bootstrap configured in
`tests/integration/conftest.py`, so they no longer depend on an external
localhost:7687 service being started manually.
"""

from datetime import datetime, timezone

from src.mcp_server.models.state_model import State, Transition


class TestNeo4jStateRepository:
    """Integration tests for the Neo4j state repository."""

    def test_create_state(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        state = State(
            state_number=0,
            user_prompt="Genesis state",
            branch_name="main",
            git_diff_info="initial diff",
            hash="abc123def456",
        )

        assert state_repo.create(state) is True

        retrieved = state_repo.get_by_number(0)
        assert retrieved is not None
        assert retrieved.state_number == 0
        assert retrieved.user_prompt == "Genesis state"
        assert retrieved.branch_name == "main"

    def test_create_multiple_states(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        for i in range(5):
            assert state_repo.create(
                State(
                    state_number=i,
                    user_prompt=f"State {i}",
                    branch_name="main",
                    git_diff_info=f"diff {i}",
                    hash=f"hash{i}",
                )
            ) is True

        assert state_repo.count() == 5
        assert len(state_repo.get_all()) == 5

    def test_get_current_state(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        for i in [0, 1, 2]:
            state_repo.create(
                State(
                    state_number=i,
                    user_prompt=f"State {i}",
                    branch_name="main",
                    git_diff_info=f"diff {i}",
                    hash=f"hash{i}",
                )
            )

        current = state_repo.get_current()
        assert current is not None
        assert current.state_number == 2

    def test_get_current_state_respects_metadata_pointing_to_zero(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        genesis = State(
            state_number=0,
            user_prompt="Genesis state",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"tracked.txt": "abc123"},
        )
        newer = State(
            state_number=1,
            user_prompt="Next state",
            branch_name="main",
            git_diff_info="diff",
            hash="hash1",
            file_hash_deltas={"tracked.txt": "def456"},
        )

        assert state_repo.create(genesis) is True
        assert state_repo.create(newer) is True
        assert state_repo.set_current(0) is True

        current = state_repo.get_current()
        assert current is not None
        assert current.state_number == 0
        assert current.file_hashes == {"tracked.txt": "abc123"}

    def test_state_exists(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        state_repo.create(
            State(
                state_number=99,
                user_prompt="Test state",
                branch_name="main",
                git_diff_info="",
                hash="hash99",
            )
        )

        assert state_repo.exists(99) is True
        assert state_repo.exists(100) is False

    def test_search_states(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        states_data = [
            (0, "Implement login feature with OAuth", "hash0"),
            (1, "Fix bug in dashboard rendering", "hash1"),
            (2, "Add user registration page", "hash2"),
            (3, "Implement login validation", "hash3"),
        ]

        for num, prompt, state_hash in states_data:
            state_repo.create(
                State(
                    state_number=num,
                    user_prompt=prompt,
                    branch_name="main",
                    git_diff_info="",
                    hash=state_hash,
                )
            )

        login_results = state_repo.search("login")
        assert len(login_results) == 2
        assert 0 in login_results
        assert 3 in login_results

        user_results = state_repo.search("user")
        assert user_results == [2]

    def test_duplicate_hash_prevention(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        state1 = State(
            state_number=0,
            user_prompt="First state",
            branch_name="main",
            git_diff_info="",
            hash="same_hash",
        )
        state2 = State(
            state_number=1,
            user_prompt="Second state with same hash",
            branch_name="develop",
            git_diff_info="different",
            hash="same_hash",
        )

        assert state_repo.create(state1) is True
        assert state_repo.create(state2) is False
        assert state_repo.count() == 1

    def test_state_roundtrip_preserves_compaction_fields(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos
        compacted_at = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)

        state = State(
            state_number=7,
            user_prompt="Compacted state",
            branch_name="main",
            git_diff_info="diff",
            hash="hash7",
            llm_context='{"v":"scc-e:v1","d":[],"h":[]}',
            compression_version="scc-e:v1",
            compacted_at=compacted_at,
        )

        assert state_repo.create(state) is True

        retrieved = state_repo.get_by_number(7)
        assert retrieved is not None
        assert retrieved.llm_context == '{"v":"scc-e:v1","d":[],"h":[]}'
        assert retrieved.compression_version == "scc-e:v1"
        assert retrieved.compacted_at == compacted_at


class TestNeo4jTransitionRepository:
    """Integration tests for the Neo4j transition repository."""

    def test_create_transition(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos

        transition = Transition(
            transition_id=1,
            current_state=0,
            next_state=1,
            user_prompt="First transition",
        )

        assert transition_repo.create(transition) is True

        retrieved = transition_repo.get_by_id(1)
        assert retrieved is not None
        assert retrieved.current_state == 0
        assert retrieved.next_state == 1

    def test_get_transitions_for_state(self, managed_neo4j_repos):
        state_repo, transition_repo = managed_neo4j_repos

        for i in range(4):
            state_repo.create(
                State(
                    state_number=i,
                    user_prompt=f"State {i}",
                    branch_name="main",
                    git_diff_info="",
                    hash=f"hash{i}",
                )
            )

        transition_repo.create(Transition(transition_id=1, current_state=0, next_state=1))
        transition_repo.create(Transition(transition_id=2, current_state=0, next_state=2))
        transition_repo.create(Transition(transition_id=3, current_state=1, next_state=3))

        assert len(transition_repo.get_by_state(0)) == 2
        assert len(transition_repo.get_by_state(1)) == 1

    def test_get_last_transitions(self, managed_neo4j_repos):
        state_repo, transition_repo = managed_neo4j_repos

        for i in range(5):
            state_repo.create(
                State(
                    state_number=i,
                    user_prompt=f"State {i}",
                    branch_name="main",
                    git_diff_info="",
                    hash=f"hash{i}",
                )
            )
        for i in range(5):
            transition_repo.create(
                Transition(
                    transition_id=i + 1,
                    current_state=i,
                    next_state=i + 1 if i < 4 else 4,
                    user_prompt=f"Transition {i}",
                )
            )

        assert len(transition_repo.get_last(3)) == 3

    def test_get_rewarded(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos

        transition_repo.create(
            Transition(
                transition_id=21,
                current_state=0,
                next_state=1,
                user_prompt="rewarded",
                reward=8.5,
            )
        )
        transition_repo.create(
            Transition(
                transition_id=22,
                current_state=1,
                next_state=2,
                user_prompt="plain",
            )
        )

        rewarded = transition_repo.get_rewarded()
        assert [transition.transition_id for transition in rewarded] == [21]
        assert rewarded[0].reward == 8.5

    def test_get_by_state_pair(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos

        transition_repo.create(Transition(transition_id=31, current_state=2, next_state=3))
        transition_repo.create(Transition(transition_id=32, current_state=2, next_state=3))
        transition_repo.create(Transition(transition_id=33, current_state=3, next_state=4))

        matches = transition_repo.get_by_state_pair(2, 3)
        assert [transition.transition_id for transition in matches] == [31, 32]

    def test_update_reward(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos

        transition_repo.create(
            Transition(
                transition_id=41,
                current_state=4,
                next_state=5,
                user_prompt="re-score me",
            )
        )

        assert transition_repo.update_reward(41, 4.0) is True
        updated = transition_repo.get_by_id(41)
        assert updated is not None
        assert updated.reward == 4.0

    def test_delete_transition(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos

        transition_repo.create(
            Transition(
                transition_id=51,
                current_state=0,
                next_state=1,
                user_prompt="Delete me",
            )
        )
        assert transition_repo.delete(51) is True
        assert transition_repo.get_by_id(51) is None


class TestNeo4jIntegrationWorkflow:
    """Integration tests for complete workflows."""

    def test_complete_state_machine_workflow(self, managed_neo4j_repos):
        state_repo, transition_repo = managed_neo4j_repos

        genesis = State(
            state_number=0,
            user_prompt="Genesis - Initial state",
            branch_name="main",
            git_diff_info="",
            hash="genesis_hash",
        )
        assert state_repo.create(genesis) is True

        for i in range(1, 4):
            assert state_repo.create(
                State(
                    state_number=i,
                    user_prompt=f"State {i} - Task {i}",
                    branch_name="main",
                    git_diff_info=f"changes for task {i}",
                    hash=f"hash{i}",
                )
            ) is True
            assert transition_repo.create(
                Transition(
                    transition_id=i,
                    current_state=i - 1,
                    next_state=i,
                    user_prompt=f"Transition to state {i}",
                )
            ) is True

        assert state_repo.count() == 4
        assert transition_repo.count() == 3
        current = state_repo.get_current()
        assert current is not None
        assert current.state_number == 3
        assert 2 in state_repo.search("Task 2")
        assert len(transition_repo.get_last(5)) == 3


class TestNeo4jConstraints:
    """Constraint and edge-case tests."""

    def test_state_number_uniqueness(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos

        state1 = State(
            state_number=42,
            user_prompt="First state 42",
            branch_name="main",
            git_diff_info="",
            hash="hash_a",
        )
        state2 = State(
            state_number=42,
            user_prompt="Second state 42",
            branch_name="develop",
            git_diff_info="different",
            hash="hash_b",
        )

        assert state_repo.create(state1) is True
        assert state_repo.create(state2) is True
        assert state_repo.count() == 1

    def test_get_nonexistent_state(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos
        assert state_repo.get_by_number(99999) is None

    def test_get_current_with_no_states(self, managed_neo4j_repos):
        state_repo, _ = managed_neo4j_repos
        assert state_repo.get_current() is None


class TestNeo4jTransitionRepositoryEdgeCases:
    """Additional edge cases for transitions."""

    def test_get_nonexistent_transition(self, managed_neo4j_repos):
        _, transition_repo = managed_neo4j_repos
        assert transition_repo.get_by_id(99999) is None
