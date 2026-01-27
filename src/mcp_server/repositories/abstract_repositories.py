from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

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

    @abstractmethod
    def delete(self, state_number: int) -> bool:
        pass

    @abstractmethod
    def create_next(self, state: State) -> bool:
        """Create a new state with the next sequential state number.

        The state_number field in the provided State object will be ignored
        and replaced with the next available sequential number.
        Returns True if successful, False otherwise.
        """
        pass


class TransitionRepository(ABC):
    @abstractmethod
    def create(self, transition: Transition) -> bool:
        pass

    @abstractmethod
    def create_next(self, transition: Transition) -> bool:
        """Create a new transition with the next sequential transition ID.

        The transition_id field in the provided Transition object will be ignored
        and replaced with the next available sequential ID.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_by_id(self, transition_id: int) -> Optional[Transition]:
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
