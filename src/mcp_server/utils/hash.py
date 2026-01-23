import hashlib
from typing import Any, Dict


def generate_state_hash(
    user_prompt: str, branch_name: str, git_diff_info: str, state_number: int
) -> str:
    content = f"{state_number}:{user_prompt}:{branch_name}:{git_diff_info}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_state_hash(
    state_hash: str, user_prompt: str, branch_name: str, git_diff_info: str, state_number: int
) -> bool:
    expected_hash = generate_state_hash(user_prompt, branch_name, git_diff_info, state_number)
    return state_hash == expected_hash
