from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from ..models.state_model import State, Transition


class StateRepository(ABC):
    @abstractmethod
    def create(self, state: State) -> bool:
        pass

    @abstractmethod
    def get_by_number(self, state_number: int) -> Optional[State]:
        pass

    @abstractmethod
    def get_current(self) -> Optional[State]:
        pass

    @abstractmethod
    def get_all(self) -> List[State]:
        pass

    @abstractmethod
    def exists(self, state_number: int) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def search(self, text: str) -> List[int]:
        pass


class TransitionRepository(ABC):
    @abstractmethod
    def create(self, transition: Transition) -> bool:
        pass

    @abstractmethod
    def get_by_id(self, transition_id: UUID) -> Optional[Transition]:
        pass

    @abstractmethod
    def get_by_state(self, state_number: int) -> List[Transition]:
        pass

    @abstractmethod
    def get_last(self, limit: int) -> List[Transition]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass
