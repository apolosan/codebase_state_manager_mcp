import tempfile
import time
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.services.state_service import StateService


class MockStateRepository:
    def __init__(self):
        self.states = {}
        self._current = None

    def create(self, state: State) -> bool:
        self.states[state.state_number] = state
        self._current = state
        return True

    def get_by_number(self, state_number: int):
        return self.states.get(state_number)

    def get_current(self):
        if self._current:
            return self._current
        if not self.states:
            return None
        max_num = max(self.states.keys())
        return self.states[max_num]

    def get_all(self):
        return [self.states[k] for k in sorted(self.states.keys())]

    def exists(self, state_number: int) -> bool:
        return state_number in self.states

    def count(self) -> int:
        return len(self.states)

    def search(self, text: str):
        return [s.state_number for s in self.states.values() if text in s.user_prompt]

    def delete(self, state_number: int) -> bool:
        if state_number in self.states:
            del self.states[state_number]
            return True
        return False

    def create_next(self, state: State) -> bool:
        # Find next sequential number
        max_num = max(self.states.keys()) if self.states else -1
        next_num = max_num + 1
        state.state_number = next_num
        # Generate a simple hash for testing
        state.hash = f"hash{next_num}"
        self.states[next_num] = state
        self._current = state
        return True


class MockTransitionRepository:
    def __init__(self):
        self.transitions = {}

    def create(self, transition: Transition) -> bool:
        self.transitions[str(transition.transition_id)] = transition
        return True

    def create_next(self, transition: Transition) -> bool:
        # Find next sequential ID
        max_id = max([int(k) for k in self.transitions.keys()]) if self.transitions else 0
        next_id = max_id + 1
        transition.transition_id = next_id
        self.transitions[str(next_id)] = transition
        return True

    def get_by_id(self, transition_id):
        return self.transitions.get(str(transition_id))

    def get_by_state(self, state_number: int):
        return [t for t in self.transitions.values() if t.current_state == state_number]

    def get_last(self, limit: int):
        all_t = list(self.transitions.values())
        return all_t[-limit:] if all_t else []

    def count(self) -> int:
        return len(self.transitions)


class TestStressTransitions:
    @pytest.fixture
    def mock_repos(self):
        return MockStateRepository(), MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.get_diff.return_value = "diff content"
        manager.compute_changes_since_last_state.return_value = (
            '{"added": [], "modified": [], "deleted": [], "content_diffs": {}}',
            {},
        )
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_repos, git_manager, settings):
        state_repo, transition_repo = mock_repos
        return StateService(
            state_repo=state_repo,
            transition_repo=transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_10k_sequential_transitions_performance(self, state_service, settings):
        from src.mcp_server.utils.init_manager import set_initialized

        tracemalloc.start()

        state_repo, transition_repo = state_service.state_repo, state_service.transition_repo

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis state - State machine initialized",
            branch_name="main",
            git_diff_info="initial diff",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        start_time = time.time()

        num_transitions = 10000
        for i in range(num_transitions):
            success, state, message = state_service.new_state_transition(f"Test transition {i}")
            assert success is True, f"Transition {i} failed: {message}"
            assert state is not None
            assert state.state_number == i + 1

        end_time = time.time()

        current, _ = state_service.get_current_state()
        assert current.state_number == num_transitions

        total_transitions = transition_repo.count()
        assert total_transitions == num_transitions

        elapsed = end_time - start_time
        avg_time_per_transition = elapsed / num_transitions

        print(f"\nPerformance Results:")
        print(f"  Total transitions: {num_transitions}")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Avg time per transition: {avg_time_per_transition*1000:.2f}ms")

        assert (
            avg_time_per_transition < 0.01
        ), f"Transition too slow: {avg_time_per_transition*1000:.2f}ms per transition"

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"  Memory usage: {current/1024/1024:.2f}MB current, {peak/1024/1024:.2f}MB peak")

        assert peak < 100 * 1024 * 1024, f"Memory leak detected: {peak/1024/1024:.2f}MB"

    def test_arbitrary_transitions_stress(self, state_service, settings):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = state_service.state_repo, state_service.transition_repo

        num_states = 100

        for i in range(num_states):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info=f"diff {i}",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        set_initialized(settings.docker_volume_name, True)

        current = state_repo.get_by_number(0)
        state_repo._current = current

        import random

        random.seed(42)

        num_jumps = 500
        for i in range(num_jumps):
            current = state_repo.get_current()
            target = random.randint(0, num_states - 1)
            if target == current.state_number:
                target = (target + 1) % num_states
            success, state, message = state_service.arbitrary_state_transition(target)

            assert success is True, f"Jump to {target} failed: {message}"
            assert state.state_number == target

        total_transitions = transition_repo.count()
        assert total_transitions == num_jumps

    def test_state_order_integrity(self, state_service, settings):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = state_service.state_repo, state_service.transition_repo

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        states_created = []
        for i in range(100):
            success, state, message = state_service.new_state_transition(f"State {i}")
            assert success is True
            states_created.append(state)

        for i, state in enumerate(states_created):
            assert state.state_number == i + 1

        all_states = state_repo.get_all()
        assert len(all_states) == 101

        for i, state in enumerate(all_states):
            assert state.state_number == i

    def test_concurrent_like_transitions(self, state_service, settings):
        import threading
        from queue import Queue

        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = state_service.state_repo, state_service.transition_repo

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        num_threads = 10
        transitions_per_thread = 100
        results = Queue()

        def worker(thread_id):
            local_success = 0
            local_fail = 0
            for i in range(transitions_per_thread):
                success, state, message = state_service.new_state_transition(
                    f"Thread {thread_id} transition {i}"
                )
                if success:
                    local_success += 1
                else:
                    local_fail += 1
            results.put((thread_id, local_success, local_fail))

        threads = []
        for t_id in range(num_threads):
            t = threading.Thread(target=worker, args=(t_id,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_success = 0
        total_fail = 0
        while not results.empty():
            thread_id, success, fail = results.get()
            total_success += success
            total_fail += fail

        assert total_success + total_fail == num_threads * transitions_per_thread

        final_state, _ = state_service.get_current_state()
        assert final_state.state_number >= num_threads * transitions_per_thread - 10
