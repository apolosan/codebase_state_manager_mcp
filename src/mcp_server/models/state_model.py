from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class State:
    def __init__(
        self,
        state_number: int,
        user_prompt: str,
        branch_name: str,
        git_diff_info: str,
        hash: str,
        created_at: Optional[datetime] = None,
        file_hashes: Optional[Dict[str, str]] = None,
    ) -> None:
        self.state_number = state_number
        self.user_prompt = user_prompt
        self.branch_name = branch_name
        self.git_diff_info = git_diff_info
        self.hash = hash
        self.created_at = created_at or now_utc()
        self.file_hashes = file_hashes or {}

    def to_dict(self) -> dict:
        return {
            "state_number": self.state_number,
            "user_prompt": self.user_prompt,
            "branch_name": self.branch_name,
            "git_diff_info": self.git_diff_info,
            "hash": self.hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "file_hashes": self.file_hashes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"])
            else:
                created_at = data["created_at"]
        return cls(
            state_number=data["state_number"],
            user_prompt=data["user_prompt"],
            branch_name=data["branch_name"],
            git_diff_info=data["git_diff_info"],
            hash=data["hash"],
            created_at=created_at,
            file_hashes=data.get("file_hashes", {}),
        )


class Transition:
    def __init__(
        self,
        transition_id: int,
        current_state: int,
        next_state: int,
        user_prompt: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.transition_id = transition_id
        self.current_state = current_state
        self.next_state = next_state
        self.user_prompt = user_prompt
        self.timestamp = timestamp or now_utc()

    def to_dict(self) -> dict:
        return {
            "transition_id": str(self.transition_id),
            "current_state": self.current_state,
            "next_state": self.next_state,
            "user_prompt": self.user_prompt,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transition":
        timestamp = None
        if data.get("timestamp"):
            if isinstance(data["timestamp"], str):
                timestamp = datetime.fromisoformat(data["timestamp"])
            else:
                timestamp = data["timestamp"]
        transition_id = data.get("transition_id")
        if transition_id is None:
            raise ValueError("transition_id is required")
        if isinstance(transition_id, str):
            transition_id = int(transition_id)
        return cls(
            transition_id=transition_id,
            current_state=data["current_state"],
            next_state=data["next_state"],
            user_prompt=data.get("user_prompt"),
            timestamp=timestamp,
        )
