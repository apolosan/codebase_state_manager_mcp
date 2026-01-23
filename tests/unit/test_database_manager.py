"""Unit tests for DatabaseManager abstract class and related structures."""

from abc import ABC, abstractmethod
from datetime import datetime
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest

from src.mcp_server.models.state_model import State, Transition


class TestStateModel:
    """Tests for State model."""

    def test_state_creation(self):
        """Test creating a State instance."""
        state = State(
            state_number=0,
            user_prompt="Test",
            branch_name="main",
            git_diff_info="diff",
            hash="abc123",
        )
        assert state.state_number == 0
        assert state.user_prompt == "Test"
        assert state.branch_name == "main"

    def test_state_with_created_at(self):
        """Test State with created_at timestamp."""
        now = datetime.now()
        state = State(
            state_number=1,
            user_prompt="Test",
            branch_name="main",
            git_diff_info="diff",
            hash="abc123",
            created_at=now,
        )
        assert state.created_at == now

    def test_state_to_dict(self):
        """Test State to_dict method."""
        state = State(
            state_number=2,
            user_prompt="Test prompt",
            branch_name="feature",
            git_diff_info="some diff",
            hash="hash123",
        )
        result = state.to_dict()
        assert result["state_number"] == 2
        assert result["user_prompt"] == "Test prompt"


class TestTransitionModel:
    """Tests for Transition model."""

    def test_transition_creation(self):
        """Test creating a Transition instance."""
        transition_id = uuid4()
        transition = Transition(
            transition_id=transition_id,
            current_state=1,
            next_state=2,
            user_prompt="Test",
        )
        assert transition.transition_id == transition_id
        assert transition.current_state == 1
        assert transition.next_state == 2

    def test_transition_with_timestamp(self):
        """Test Transition with timestamp."""
        now = datetime.now()
        transition = Transition(
            transition_id=uuid4(),
            current_state=0,
            next_state=1,
            user_prompt="Initial",
            timestamp=now,
        )
        assert transition.timestamp == now

    def test_transition_to_dict(self):
        """Test Transition to_dict method."""
        transition_id = uuid4()
        transition = Transition(
            transition_id=transition_id,
            current_state=1,
            next_state=2,
            user_prompt="Transition",
        )
        result = transition.to_dict()
        assert result["transition_id"] == str(transition_id)
        assert result["current_state"] == 1
        assert result["next_state"] == 2


class TestDatabaseManagerAbstract:
    """Tests for DatabaseManager abstract class structure."""

    def test_database_manager_is_abstract(self):
        """Test that DatabaseManager is an abstract class."""
        from src.mcp_server.models.database_manager import DatabaseManager

        assert issubclass(DatabaseManager, ABC)

    def test_abstract_methods_defined(self):
        """Test that all required abstract methods are defined."""
        from src.mcp_server.models.database_manager import DatabaseManager

        abstract_methods = [
            "initialize",
            "close",
            "create_state",
            "get_state",
            "get_current_state",
            "get_all_states",
            "state_exists",
            "create_transition",
            "get_transitions_for_state",
            "get_transition",
            "get_last_transitions",
            "search_states",
            "get_total_states",
            "is_initialized",
            "set_initialized",
        ]
        for method in abstract_methods:
            attr = getattr(DatabaseManager, method, None)
            assert attr is not None, f"Missing method: {method}"
            assert getattr(attr, "__isabstractmethod__", False), f"Method {method} is not abstract"
