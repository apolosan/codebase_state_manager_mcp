from typing import Optional
from uuid import uuid4
from pathlib import Path

from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..services.git_manager import GitManager
from ..utils.hash import generate_state_hash
from ..utils.init_manager import is_initialized, set_initialized
from ..config import Settings


class StateService:
    def __init__(
        self,
        state_repo: StateRepository,
        transition_repo: TransitionRepository,
        git_manager: GitManager,
        settings: Settings,
    ) -> None:
        self.state_repo = state_repo
        self.transition_repo = transition_repo
        self.git_manager = git_manager
        self.settings = settings

    def genesis(
        self,
        project_path: str,
        volume_path: str,
        current_branch: Optional[str] = None,
        current_diff: Optional[str] = None,
    ) -> tuple[bool, Optional[State], str]:
        if is_initialized(volume_path):
            return False, None, "State manager already initialized. Call reset first."

        source_path = Path(project_path)
        Path(volume_path).mkdir(parents=True, exist_ok=True)
        target_path = Path(volume_path) / "codebase"

        if self.git_manager.is_git_repo(source_path):
            if not self.git_manager.clone_to_volume(source_path, target_path):
                return False, None, "Failed to clone repository to volume"
            branch_name = current_branch or self.git_manager.get_current_branch()
            diff_info = current_diff or self.git_manager.get_diff(repo_path=target_path)
        else:
            if not self.git_manager.clone_to_volume(source_path, target_path):
                return False, None, "Failed to clone files to volume"
            if not self.git_manager.init_repo(target_path):
                return False, None, "Failed to initialize git repository"
            self.git_manager.create_branch("codebase-state-machine", target_path)
            branch_name = "codebase-state-machine"
            diff_info = ""

        state_0 = State(
            state_number=0,
            user_prompt="Genesis state - State machine initialized",
            branch_name=branch_name,
            git_diff_info=diff_info,
            hash="",
        )
        state_0.hash = generate_state_hash(
            state_0.user_prompt, state_0.branch_name, state_0.git_diff_info, state_0.state_number
        )

        if not self.state_repo.create(state_0):
            return False, None, "Failed to save genesis state"

        self.settings.docker_volume_name = volume_path

        if not set_initialized(volume_path, True):
            return False, None, "Failed to set initialized flag"

        return True, state_0, "Genesis state created successfully"

    def new_state_transition(
        self, user_prompt: str, current_diff: Optional[str] = None
    ) -> tuple[bool, Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        current_state = self.state_repo.get_current()
        if not current_state:
            return False, None, "No current state found. Call genesis first."

        next_state_number = self.state_repo.count()
        branch_name = current_state.branch_name
        diff_info = current_diff or self.git_manager.get_diff(repo_path=Path(self.settings.docker_volume_name) / "codebase")

        new_state = State(
            state_number=next_state_number,
            user_prompt=user_prompt,
            branch_name=branch_name,
            git_diff_info=diff_info,
            hash="",
        )
        new_state.hash = generate_state_hash(
            new_state.user_prompt, new_state.branch_name, new_state.git_diff_info, new_state.state_number
        )

        if not self.state_repo.create(new_state):
            return False, None, "Failed to create new state"

        transition = Transition(
            transition_id=uuid4(),
            current_state=current_state.state_number,
            next_state=new_state.state_number,
            user_prompt=user_prompt,
        )
        if not self.transition_repo.create(transition):
            return False, None, "Failed to create transition"

        return True, new_state, f"Transition to state {next_state_number} successful"

    def arbitrary_state_transition(
        self, next_state: int, user_prompt: Optional[str] = None
    ) -> tuple[bool, Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        current_state = self.state_repo.get_current()
        if not current_state:
            return False, None, "No current state found. Call genesis first."

        if next_state < 0 or next_state >= self.state_repo.count():
            return False, None, f"Invalid state number: {next_state}"

        target_state = self.state_repo.get_by_number(next_state)
        if not target_state:
            return False, None, f"State {next_state} not found"

        transition_prompt = user_prompt or "Arbitrary transition"
        if not target_state.user_prompt or target_state.user_prompt == "Arbitrary transition":
            target_state.user_prompt = transition_prompt

        transition = Transition(
            transition_id=uuid4(),
            current_state=current_state.state_number,
            next_state=target_state.state_number,
            user_prompt=transition_prompt,
        )
        if not self.transition_repo.create(transition):
            return False, None, "Failed to create transition"

        return True, target_state, f"Arbitrary transition to state {next_state} successful"

    def get_current_state(self) -> tuple[Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_current()
        if state:
            return state, "Current state retrieved"
        return None, "No state found"

    def get_current_state_number(self) -> tuple[Optional[int], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_current()
        if state:
            return state.state_number, "Current state number retrieved"
        return None, "No state found"

    def get_state_info(self, state_number: int) -> tuple[Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_by_number(state_number)
        if state:
            return state, f"State {state_number} info retrieved"
        return None, f"State {state_number} not found"

    def total_states(self) -> tuple[int, str]:
        if not is_initialized(self.settings.docker_volume_name):
            return 0, "State manager not initialized. Call genesis first."
        return self.state_repo.count(), "Total states count retrieved"

    def search_states(self, text: str) -> tuple[list[int], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        results = self.state_repo.search(text)
        return results, f"Found {len(results)} states matching '{text}'"

    def get_state_transitions(self, state_number: int) -> tuple[list, str]:
        if not is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        transitions = self.transition_repo.get_by_state(state_number)
        return [str(t.transition_id) for t in transitions], f"Transitions for state {state_number} retrieved"

    def get_transition_info(self, transition_id: str) -> tuple[Optional[dict], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        try:
            from uuid import UUID
            transition = self.transition_repo.get_by_id(UUID(transition_id))
            if transition:
                return transition.to_dict(), f"Transition {transition_id} info retrieved"
            return None, f"Transition {transition_id} not found"
        except ValueError:
            return None, f"Invalid transition ID format: {transition_id}"

    def track_transitions(self) -> tuple[list, str]:
        if not is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        transitions = self.transition_repo.get_last(5)
        return [str(t.transition_id) for t in transitions], "Last 5 transitions retrieved"
