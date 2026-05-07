from datetime import datetime, timezone

from src.mcp_server.models.state_model import State, Transition


VALID_LLM_CONTEXT = '{"v":"scc-e:v1","d":[{"p":1,"a":"M","s":42}],"h":[{"i":1,"h":"abc123=="}]}'


class TestStateModelExtensions:
    def test_state_init_defaults_new_compaction_fields_to_none(self):
        state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="",
            hash="hash0",
        )

        assert state.llm_context is None
        assert state.compression_version is None
        assert state.compacted_at is None

    def test_state_init_accepts_new_compaction_fields(self):
        compacted_at = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)
        state = State(
            state_number=1,
            user_prompt="Compact state",
            branch_name="main",
            git_diff_info="diff",
            hash="hash1",
            llm_context=VALID_LLM_CONTEXT,
            compression_version="scc-e:v1",
            compacted_at=compacted_at,
        )

        assert state.llm_context == VALID_LLM_CONTEXT
        assert state.compression_version == "scc-e:v1"
        assert state.compacted_at == compacted_at

    def test_state_to_dict_includes_compaction_fields(self):
        compacted_at = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)
        state = State(
            state_number=2,
            user_prompt="Compact state",
            branch_name="main",
            git_diff_info="diff",
            hash="hash2",
            llm_context=VALID_LLM_CONTEXT,
            compression_version="scc-e:v1",
            compacted_at=compacted_at,
        )

        result = state.to_dict()

        assert result["llm_context"] == VALID_LLM_CONTEXT
        assert result["compression_version"] == "scc-e:v1"
        assert result["compacted_at"] == compacted_at.isoformat()

    def test_state_from_dict_restores_compaction_fields(self):
        compacted_at = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)
        state = State.from_dict(
            {
                "state_number": 3,
                "user_prompt": "Compact state",
                "branch_name": "main",
                "git_diff_info": "diff",
                "hash": "hash3",
                "llm_context": VALID_LLM_CONTEXT,
                "compression_version": "scc-e:v1",
                "compacted_at": compacted_at.isoformat(),
            }
        )

        assert state.llm_context == VALID_LLM_CONTEXT
        assert state.compression_version == "scc-e:v1"
        assert state.compacted_at == compacted_at

    def test_state_from_dict_remains_backward_compatible_without_new_fields(self):
        state = State.from_dict(
            {
                "state_number": 4,
                "user_prompt": "Legacy state",
                "branch_name": "main",
                "git_diff_info": "diff",
                "hash": "hash4",
            }
        )

        assert state.llm_context is None
        assert state.compression_version is None
        assert state.compacted_at is None

    def test_state_to_dict_and_from_dict_roundtrip_preserves_new_fields(self):
        compacted_at = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)
        original = State(
            state_number=5,
            user_prompt="Roundtrip",
            branch_name="main",
            git_diff_info="diff",
            hash="hash5",
            llm_context=VALID_LLM_CONTEXT,
            compression_version="scc-e:v1",
            compacted_at=compacted_at,
        )

        restored = State.from_dict(original.to_dict())

        assert restored.to_dict()["llm_context"] == VALID_LLM_CONTEXT
        assert restored.compression_version == "scc-e:v1"
        assert restored.compacted_at == compacted_at


class TestTransitionModelExtensions:
    def test_transition_init_defaults_reward_to_none(self):
        transition = Transition(
            transition_id=1,
            current_state=0,
            next_state=1,
            user_prompt="Initial transition",
        )

        assert transition.reward is None

    def test_transition_init_accepts_reward(self):
        transition = Transition(
            transition_id=2,
            current_state=1,
            next_state=2,
            user_prompt="Rewarded transition",
            reward=7.5,
        )

        assert transition.reward == 7.5

    def test_transition_to_dict_includes_reward_when_present(self):
        transition = Transition(
            transition_id=3,
            current_state=2,
            next_state=3,
            user_prompt="Rewarded transition",
            reward=7.5,
        )

        result = transition.to_dict()

        assert result["reward"] == 7.5

    def test_transition_to_dict_keeps_reward_key_when_none(self):
        transition = Transition(
            transition_id=4,
            current_state=3,
            next_state=4,
            user_prompt="Legacy transition",
        )

        result = transition.to_dict()

        assert "reward" in result
        assert result["reward"] is None

    def test_transition_from_dict_restores_reward(self):
        transition = Transition.from_dict(
            {
                "transition_id": 5,
                "current_state": 4,
                "next_state": 5,
                "user_prompt": "Rewarded transition",
                "reward": -3.5,
            }
        )

        assert transition.reward == -3.5

    def test_transition_from_dict_remains_backward_compatible_without_reward(self):
        transition = Transition.from_dict(
            {
                "transition_id": 6,
                "current_state": 5,
                "next_state": 6,
                "user_prompt": "Legacy transition",
            }
        )

        assert transition.reward is None
