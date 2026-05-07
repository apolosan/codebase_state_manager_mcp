import json

from src.mcp_server.models.state_model import State
from src.mcp_server.services.scc_codec import (
    PATH_VOCAB_METADATA_KEY,
    PATH_VOCAB_REVISION_METADATA_KEY,
    append_new_paths_to_vocab,
    build_current_state_preview,
    encode_state_for_llm,
    load_or_build_vocab,
)
from src.mcp_server.utils.validation import validate_llm_context


class FakeStateRepository:
    def __init__(self, states: list[State] | None = None):
        self._states = states or []
        self.metadata: dict[str, str] = {}

    def get_all(self) -> list[State]:
        return list(self._states)

    def get_metadata(self, key: str) -> str | None:
        return self.metadata.get(key)

    def set_metadata(self, key: str, value: str) -> bool:
        self.metadata[key] = value
        return True


class TestSccCodec:
    def test_load_or_build_vocab_bootstraps_from_existing_states(self):
        state_repo = FakeStateRepository(
            states=[
                State(
                    state_number=0,
                    user_prompt="Genesis",
                    branch_name="main",
                    git_diff_info="",
                    hash="hash0",
                    file_hashes={"src/app.py": "a" * 64, "README.md": "b" * 64},
                    file_hash_deltas={"src/app.py": "a" * 64, "README.md": "b" * 64},
                ),
                State(
                    state_number=1,
                    user_prompt="Change",
                    branch_name="main",
                    git_diff_info=json.dumps(
                        {
                            "added": ["docs/guide.md"],
                            "modified": ["src/app.py"],
                            "deleted": ["old.txt"],
                            "content_diffs": {
                                "docs/guide.md": "guide",
                                "src/app.py": "@@ -1 +1 @@\n-print('x')\n+print('y')",
                            },
                        }
                    ),
                    hash="hash1",
                    file_hash_deltas={
                        "docs/guide.md": "c" * 64,
                        "src/app.py": "d" * 64,
                        "old.txt": None,
                    },
                ),
            ]
        )

        vocab, revision = load_or_build_vocab(state_repo)

        assert set(vocab) == {"README.md", "docs/guide.md", "old.txt", "src/app.py"}
        assert revision == 1
        assert PATH_VOCAB_METADATA_KEY in state_repo.metadata
        assert PATH_VOCAB_REVISION_METADATA_KEY in state_repo.metadata

    def test_append_new_paths_to_vocab_preserves_existing_ids(self):
        state_repo = FakeStateRepository()
        vocab, _ = load_or_build_vocab(state_repo)
        vocab, revision = append_new_paths_to_vocab(state_repo, vocab, ["src/app.py", "README.md"])
        original_app_id = vocab["src/app.py"]

        updated_vocab, updated_revision = append_new_paths_to_vocab(
            state_repo,
            dict(vocab),
            ["src/app.py", "docs/guide.md"],
        )

        assert updated_vocab["src/app.py"] == original_app_id
        assert updated_vocab["docs/guide.md"] > max(vocab.values())
        assert updated_revision == revision + 1

    def test_encode_state_for_llm_generates_valid_payload(self):
        state_repo = FakeStateRepository()
        compact_payload = encode_state_for_llm(
            state_repo=state_repo,
            git_diff_info=json.dumps(
                {
                    "added": ["README.md"],
                    "modified": ["src/app.py"],
                    "deleted": ["old.txt"],
                    "content_diffs": {
                        "README.md": "hello",
                        "src/app.py": "@@ -1 +1 @@\n-print('x')\n+print('y')",
                    },
                }
            ),
            file_hashes={"README.md": "a" * 64, "src/app.py": "b" * 64},
        )

        validate_llm_context(compact_payload["llm_context"])
        decoded = json.loads(compact_payload["llm_context"])

        assert decoded["v"] == "scc-e:v1"
        assert len(decoded["d"]) == 3
        assert len(decoded["h"]) == 2
        assert compact_payload["compression_version"] == "scc-e:v1"
        assert compact_payload["compacted_at"] is not None

    def test_build_current_state_preview_includes_vocabulary_when_requested(self):
        state_repo = FakeStateRepository()

        preview = build_current_state_preview(
            state_repo=state_repo,
            git_diff_info=json.dumps(
                {
                    "added": ["README.md"],
                    "modified": [],
                    "deleted": [],
                    "content_diffs": {"README.md": "hello"},
                }
            ),
            file_hashes={"README.md": "a" * 64},
            include_vocabulary=True,
        )

        assert preview["persisted"] is False
        assert preview["vocabulary"] == {"README.md": 0}
        assert preview["vocab_revision"] == 2
