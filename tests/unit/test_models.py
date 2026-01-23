from datetime import datetime

import pytest

from src.mcp_server.models.state_model import State, Transition


class TestStateModel:
    def test_state_creation(self):
        state = State(
            state_number=0,
            user_prompt="Test prompt",
            branch_name="main",
            git_diff_info="",
            hash="abc123",
        )
        assert state.state_number == 0
        assert state.user_prompt == "Test prompt"
        assert state.branch_name == "main"
        assert state.hash == "abc123"

    def test_state_to_dict(self):
        state = State(
            state_number=1,
            user_prompt="Test prompt",
            branch_name="main",
            git_diff_info="diff content",
            hash="def456",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        result = state.to_dict()
        assert result["state_number"] == 1
        assert result["user_prompt"] == "Test prompt"
        assert result["branch_name"] == "main"
        assert result["git_diff_info"] == "diff content"
        assert result["hash"] == "def456"

    def test_state_from_dict(self):
        data = {
            "state_number": 2,
            "user_prompt": "From dict prompt",
            "branch_name": "develop",
            "git_diff_info": "some diff",
            "hash": "hash123",
            "created_at": "2024-01-01T12:00:00",
        }
        state = State.from_dict(data)
        assert state.state_number == 2
        assert state.user_prompt == "From dict prompt"
        assert state.branch_name == "develop"


class TestTransitionModel:
    def test_transition_creation(self):
        transition_id = 1
        transition = Transition(
            transition_id=transition_id,
            current_state=0,
            next_state=1,
            user_prompt="Test transition",
        )
        assert transition.current_state == 0
        assert transition.next_state == 1
        assert transition.user_prompt == "Test transition"

    def test_transition_to_dict(self):
        transition_id = 1
        transition = Transition(
            transition_id=transition_id,
            current_state=1,
            next_state=2,
            user_prompt="Transition to state 2",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )
        result = transition.to_dict()
        assert result["current_state"] == 1
        assert result["next_state"] == 2
        assert result["user_prompt"] == "Transition to state 2"

    def test_transition_from_dict(self):
        transition_id = 1
        data = {
            "transition_id": transition_id,
            "current_state": 2,
            "next_state": 3,
            "user_prompt": "Another transition",
            "timestamp": "2024-01-01T12:00:00",
        }
        transition = Transition.from_dict(data)
        assert transition.current_state == 2
        assert transition.next_state == 3
        assert transition.user_prompt == "Another transition"
