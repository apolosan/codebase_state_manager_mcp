"""SCC-E compact state encoding helpers."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import TypedDict

from ..models.state_model import State
from ..repositories.abstract_repositories import StateRepository
from ..utils.validation import validate_llm_context

SCC_E_VERSION = "scc-e:v1"
PATH_VOCAB_METADATA_KEY = "scc_e_path_vocab"
PATH_VOCAB_REVISION_METADATA_KEY = "scc_e_vocab_revision"
PATH_VOCAB_FORMAT_METADATA_KEY = "scc_e_vocab_format"
PATH_VOCAB_FORMAT = "json:path->id:v1"


class DiffInfo(TypedDict):
    added: list[str]
    modified: list[str]
    deleted: list[str]
    content_diffs: dict[str, str]


class EncodedDiffItem(TypedDict):
    p: int
    a: str
    s: int


class EncodedHashItem(TypedDict):
    i: int
    h: str


class CompactStatePayload(TypedDict):
    llm_context: str
    compression_version: str
    compacted_at: datetime
    vocab_revision: int


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_diff_info(git_diff_info: str | None) -> DiffInfo:
    if not git_diff_info:
        return {"added": [], "modified": [], "deleted": [], "content_diffs": {}}

    try:
        parsed = json.loads(git_diff_info)
    except json.JSONDecodeError:
        return {"added": [], "modified": [], "deleted": [], "content_diffs": {}}

    if not isinstance(parsed, dict):
        return {"added": [], "modified": [], "deleted": [], "content_diffs": {}}

    added_raw: object = parsed.get("added")
    modified_raw: object = parsed.get("modified")
    deleted_raw: object = parsed.get("deleted")
    content_diffs_raw: object = parsed.get("content_diffs")

    added = [str(path) for path in added_raw] if isinstance(added_raw, list) else []
    modified = [str(path) for path in modified_raw] if isinstance(modified_raw, list) else []
    deleted = [str(path) for path in deleted_raw] if isinstance(deleted_raw, list) else []
    content_diffs = (
        {str(path): str(content) for path, content in content_diffs_raw.items()}
        if isinstance(content_diffs_raw, dict)
        else {}
    )

    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "content_diffs": content_diffs,
    }


def _extract_paths_from_state(state: State) -> set[str]:
    paths: set[str] = set()
    paths.update(state.file_hashes or {})
    paths.update(state.file_hash_deltas or {})

    diff_info = _parse_diff_info(state.git_diff_info)
    paths.update(diff_info["added"])
    paths.update(diff_info["modified"])
    paths.update(diff_info["deleted"])
    content_diffs = diff_info["content_diffs"]
    if isinstance(content_diffs, dict):
        paths.update(content_diffs)
    return paths


def _extract_paths(git_diff_info: str | None, file_hashes: dict[str, str]) -> set[str]:
    paths = set(file_hashes)
    diff_info = _parse_diff_info(git_diff_info)
    paths.update(diff_info["added"])
    paths.update(diff_info["modified"])
    paths.update(diff_info["deleted"])
    content_diffs = diff_info["content_diffs"]
    if isinstance(content_diffs, dict):
        paths.update(content_diffs)
    return paths


def _persist_vocab(state_repo: StateRepository, vocab: dict[str, int], revision: int) -> None:
    serialized_vocab = json.dumps(dict(sorted(vocab.items(), key=lambda item: item[1])))
    state_repo.set_metadata(PATH_VOCAB_METADATA_KEY, serialized_vocab)
    state_repo.set_metadata(PATH_VOCAB_REVISION_METADATA_KEY, str(revision))
    state_repo.set_metadata(PATH_VOCAB_FORMAT_METADATA_KEY, PATH_VOCAB_FORMAT)


def load_or_build_vocab(state_repo: StateRepository) -> tuple[dict[str, int], int]:
    """Load the shared path vocabulary or build it from persisted states."""
    serialized_vocab = state_repo.get_metadata(PATH_VOCAB_METADATA_KEY)
    serialized_revision = state_repo.get_metadata(PATH_VOCAB_REVISION_METADATA_KEY)

    if isinstance(serialized_vocab, str) and serialized_vocab:
        parsed_vocab = json.loads(serialized_vocab)
        if not isinstance(parsed_vocab, dict):
            raise ValueError("Invalid SCC-E vocabulary payload")
        vocab = {str(path): int(identifier) for path, identifier in parsed_vocab.items()}
        revision = int(serialized_revision) if isinstance(serialized_revision, str) else 1
        return vocab, revision

    discovered_paths: set[str] = set()
    persisted_states = state_repo.get_all()
    if not isinstance(persisted_states, list):
        persisted_states = []
    for state in persisted_states:
        discovered_paths.update(_extract_paths_from_state(state))

    vocab = {path: index for index, path in enumerate(sorted(discovered_paths))}
    revision = 1
    _persist_vocab(state_repo, vocab, revision)
    return vocab, revision


def append_new_paths_to_vocab(
    state_repo: StateRepository,
    vocab: dict[str, int],
    paths: list[str] | set[str],
) -> tuple[dict[str, int], int]:
    """Append new paths to the shared vocabulary without renumbering older IDs."""
    existing_revision = state_repo.get_metadata(PATH_VOCAB_REVISION_METADATA_KEY)
    current_revision = int(existing_revision) if isinstance(existing_revision, str) else 1
    missing_paths = sorted({str(path) for path in paths if str(path) not in vocab})
    if not missing_paths:
        return vocab, current_revision

    next_identifier = max(vocab.values(), default=-1) + 1
    updated_vocab = dict(vocab)
    for path in missing_paths:
        updated_vocab[path] = next_identifier
        next_identifier += 1

    next_revision = current_revision + 1
    _persist_vocab(state_repo, updated_vocab, next_revision)
    return updated_vocab, next_revision


def _hex_to_base64(hex_hash: str) -> str:
    try:
        return base64.b64encode(bytes.fromhex(hex_hash)).decode("ascii")
    except ValueError:
        return base64.b64encode(hex_hash.encode("utf-8")).decode("ascii")


def encode_git_diff_for_llm(
    git_diff_info: str | None,
    vocab: dict[str, int],
) -> list[EncodedDiffItem]:
    """Encode structured diff metadata for LLM consumption."""
    diff_info = _parse_diff_info(git_diff_info)
    content_diffs = diff_info["content_diffs"]
    if not isinstance(content_diffs, dict):
        content_diffs = {}

    items: list[EncodedDiffItem] = []
    seen_paths: set[str] = set()

    for path_str in diff_info["added"]:
        seen_paths.add(path_str)
        items.append(
            {
                "p": vocab[path_str],
                "a": "A",
                "s": len(content_diffs.get(path_str, "").encode("utf-8")),
            }
        )

    for path_str in diff_info["modified"]:
        seen_paths.add(path_str)
        items.append(
            {
                "p": vocab[path_str],
                "a": "M",
                "s": len(content_diffs.get(path_str, "").encode("utf-8")),
            }
        )

    for path_str in diff_info["deleted"]:
        seen_paths.add(path_str)
        items.append(
            {
                "p": vocab[path_str],
                "a": "D",
                "s": 0,
            }
        )

    orphan_paths = sorted(set(content_diffs) - seen_paths)
    for path in orphan_paths:
        items.append(
            {
                "p": vocab[path],
                "a": "M",
                "s": len(content_diffs[path].encode("utf-8")),
            }
        )

    return sorted(items, key=lambda item: (int(item["p"]), str(item["a"])))


def encode_hashes_for_llm(
    file_hashes: dict[str, str],
    vocab: dict[str, int],
) -> list[EncodedHashItem]:
    """Encode hash snapshots using compact path IDs and base64 hashes."""
    encoded: list[EncodedHashItem] = []
    for path, hash_value in sorted(file_hashes.items(), key=lambda item: vocab[item[0]]):
        encoded.append({"i": vocab[path], "h": _hex_to_base64(hash_value)})
    return encoded


def encode_state_for_llm(
    state_repo: StateRepository,
    git_diff_info: str | None,
    file_hashes: dict[str, str],
) -> CompactStatePayload:
    """Build an SCC-E payload and persist vocabulary changes when necessary."""
    vocab, revision = load_or_build_vocab(state_repo)
    discovered_paths = _extract_paths(git_diff_info, file_hashes)
    vocab, revision = append_new_paths_to_vocab(state_repo, vocab, discovered_paths)

    payload = {
        "v": SCC_E_VERSION,
        "d": encode_git_diff_for_llm(git_diff_info, vocab),
        "h": encode_hashes_for_llm(file_hashes, vocab),
    }
    llm_context = json.dumps(payload, separators=(",", ":"))
    validate_llm_context(llm_context)
    compacted_at = _now_utc()
    return {
        "llm_context": llm_context,
        "compression_version": SCC_E_VERSION,
        "compacted_at": compacted_at,
        "vocab_revision": revision,
    }


def build_current_state_preview(
    state_repo: StateRepository,
    git_diff_info: str | None,
    file_hashes: dict[str, str],
    include_vocabulary: bool = False,
) -> dict[str, object]:
    """Build a non-persisted compact preview for the current workspace."""
    compact_payload = encode_state_for_llm(
        state_repo=state_repo,
        git_diff_info=git_diff_info,
        file_hashes=file_hashes,
    )
    preview: dict[str, object] = {
        "compression_version": compact_payload["compression_version"],
        "llm_context": compact_payload["llm_context"],
        "compacted_at": compact_payload["compacted_at"],
        "vocab_revision": compact_payload["vocab_revision"],
        "persisted": False,
    }
    if include_vocabulary:
        vocab, _ = load_or_build_vocab(state_repo)
        preview["vocabulary"] = dict(sorted(vocab.items(), key=lambda item: item[1]))
    return preview
