from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from .state_model import State, Transition


class DatabaseManager(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def create_state(self, state: State) -> bool:
        pass

    @abstractmethod
    def get_state(self, state_number: int) -> Optional[State]:
        pass

    @abstractmethod
    def get_current_state(self) -> Optional[State]:
        pass

    @abstractmethod
    def get_all_states(self) -> List[State]:
        pass

    @abstractmethod
    def state_exists(self, state_number: int) -> bool:
        pass

    @abstractmethod
    def create_transition(self, transition: Transition) -> bool:
        pass

    @abstractmethod
    def get_transitions_for_state(self, state_number: int) -> List[Transition]:
        pass

    @abstractmethod
    def get_transition(self, transition_id: UUID) -> Optional[Transition]:
        pass

    @abstractmethod
    def get_last_transitions(self, limit: int) -> List[Transition]:
        pass

    @abstractmethod
    def search_states(self, text: str) -> List[int]:
        pass

    @abstractmethod
    def get_total_states(self) -> int:
        pass

    @abstractmethod
    def is_initialized(self) -> bool:
        pass

    @abstractmethod
    def set_initialized(self, initialized: bool) -> None:
        pass
