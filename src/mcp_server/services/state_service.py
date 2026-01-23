from pathlib import Path
from typing import Optional

from ..config import Settings
from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..services.git_manager import GitManager, GitOperationError
from ..utils.audit import get_audit_logger
from ..utils.hash import generate_state_hash
from ..utils.init_manager import is_initialized, set_initialized
from ..utils.security import RateLimitExceeded, get_rate_limiter
from ..utils.validation import (
    ValidationError,
    sanitize_prompt,
    validate_state_number,
    validate_state_range,
)


class StateServiceError(Exception):
    """Exceção para erros no StateService."""

    pass


class StateNotFoundError(StateServiceError):
    """Exceção para estado não encontrado."""

    pass


class InvalidStateTransitionError(StateServiceError):
    """Exceção para transição de estado inválida."""

    pass


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
        self._audit_logger = None

    @property
    def audit_logger(self):
        """Lazy initialization of audit logger."""
        if self._audit_logger is None:
            self._audit_logger = get_audit_logger()
        return self._audit_logger

    def genesis(
        self,
        project_path: str,
        volume_path: str,
        current_branch: Optional[str] = None,
        current_diff: Optional[str] = None,
    ) -> tuple[bool, Optional[State], str]:
        if is_initialized(volume_path):
            return False, None, "State manager already initialized. Call reset first."

        try:
            source_path = Path(project_path)
            Path(volume_path).mkdir(parents=True, exist_ok=True)
            target_path = Path(volume_path) / "codebase"

            if self.git_manager.is_git_repo(source_path):
                if not self.git_manager.clone_to_volume(source_path, target_path):
                    return False, None, "Failed to clone repository to volume"
                if not self.git_manager.init_repo(target_path):
                    return False, None, "Failed to initialize git repository in volume"
                branch_name = current_branch or self.git_manager.get_current_branch(
                    repo_path=source_path
                )
                diff_info = current_diff or ""
            else:
                if not self.git_manager.clone_to_volume(source_path, target_path):
                    return False, None, "Failed to clone files to volume"
                if not self.git_manager.init_repo(target_path):
                    return False, None, "Failed to initialize git repository"
                self.git_manager.create_branch("codebase-state-machine", target_path)
                branch_name = "codebase-state-machine"
                diff_info = ""

            file_hashes = self.git_manager.get_directory_hashes(source_path)

            state_0 = State(
                state_number=0,
                user_prompt="Genesis state - State machine initialized",
                branch_name=branch_name,
                git_diff_info=diff_info,
                hash="",
                file_hashes=file_hashes,
            )
            state_0.hash = generate_state_hash(
                state_0.user_prompt,
                state_0.branch_name,
                state_0.git_diff_info,
                state_0.state_number,
            )

            if not self.state_repo.create(state_0):
                return False, None, "Failed to save genesis state"

            self.settings.docker_volume_name = volume_path

            if not set_initialized(volume_path, True):
                return False, None, "Failed to set initialized flag"

            return True, state_0, "Genesis state created successfully"
        except GitOperationError as e:
            return False, None, f"Git operation error: {e}"
        except (OSError, ValueError) as e:
            return False, None, f"Filesystem error: {e}"

    def _create_state_and_transition_atomic(
        self,
        user_prompt: str,
        diff_info: str,
        current_state: State,
        file_hashes: dict,
    ) -> tuple[bool, Optional[State], str]:
        try:
            sanitized_prompt = sanitize_prompt(user_prompt)
        except ValidationError as e:
            return False, None, f"Invalid prompt: {e}"

        next_state_number = self.state_repo.count()

        new_state = State(
            state_number=next_state_number,
            user_prompt=sanitized_prompt,
            branch_name=current_state.branch_name,
            git_diff_info=diff_info,
            hash="",
            file_hashes=file_hashes,
        )
        new_state.hash = generate_state_hash(
            new_state.user_prompt,
            new_state.branch_name,
            new_state.git_diff_info,
            new_state.state_number,
        )

        try:
            if not self.state_repo.create(new_state):
                return False, None, "Failed to create new state"

            transition = Transition(
                transition_id=self.transition_repo.count() + 1,
                current_state=current_state.state_number,
                next_state=new_state.state_number,
                user_prompt=sanitized_prompt,
            )
            if not self.transition_repo.create(transition):
                self.state_repo.create(new_state)
                return False, None, "Failed to create transition, state rolled back"

            return True, new_state, f"Transition to state {next_state_number} successful"
        except Exception as e:
            return False, None, f"Atomic operation failed: {e}"

    def new_state_transition(self, user_prompt: str) -> tuple[bool, Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        current_state = self.state_repo.get_current()
        if not current_state:
            return False, None, "No current state found. Call genesis first."

        volume_codebase = Path(self.settings.docker_volume_name) / "codebase"
        project_path = Path.cwd()

        last_hashes = getattr(current_state, "file_hashes", {}) or {}
        if not last_hashes and volume_codebase.exists():
            last_hashes = self.git_manager.get_directory_hashes(volume_codebase)
        diff_info, delta_hashes = self.git_manager.compute_changes_since_last_state(
            project_path=project_path,
            last_state_file_hashes=last_hashes,
            volume_codebase_path=volume_codebase if volume_codebase.exists() else None,
        )

        # Optimization: Merge the delta hashes with the previous state's hashes to form the new full map,
        # ensuring only changed/new files are re-evaluated/stored in the delta from git_manager,
        # while the State object itself maintains the complete set (for future base comparison).
        current_hashes = last_hashes.copy()
        current_hashes.update(delta_hashes)

        success, new_state, message = self._create_state_and_transition_atomic(
            user_prompt, diff_info, current_state, current_hashes
        )

        if success and new_state:
            try:
                if volume_codebase.exists() and project_path.exists():
                    self.git_manager.sync_project_to_volume(
                        source_path=project_path,
                        volume_path=volume_codebase,
                        sync_git=True,
                    )
            except (GitOperationError, OSError) as e:
                # Log the sync failure but continue, as the state was created successfully
                import logging

                logging.warning(
                    f"Failed to sync project to volume after state {new_state.state_number}: {e}"
                )
                from ..utils.audit import AuditEvent, AuditEventType, AuditOutcome

                error_event = AuditEvent(
                    event_type=AuditEventType.ERROR,
                    outcome=AuditOutcome.FAILURE,
                    operation=f"sync_after_state_{new_state.state_number}",
                    state_number=new_state.state_number,
                    error_message=str(e),
                )
                self.audit_logger.log_event(error_event)

        return success, new_state, message

    def arbitrary_state_transition(
        self, next_state: int, user_prompt: Optional[str] = None
    ) -> tuple[bool, Optional[State], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        current_state = self.state_repo.get_current()
        if not current_state:
            return False, None, "No current state found. Call genesis first."

        max_states = self.state_repo.count()

        try:
            validate_state_number(next_state, max_states)
        except ValidationError as e:
            return False, None, f"Invalid state number: {e}"

        target_state = self.state_repo.get_by_number(next_state)
        if not target_state:
            return False, None, f"State {next_state} not found"

        try:
            if current_state.state_number != next_state:
                validate_state_range(current_state.state_number, next_state, max_states)
        except ValidationError as e:
            return False, None, f"Invalid transition: {e}"

        transition_prompt = user_prompt or "Arbitrary transition"
        if not target_state.user_prompt or target_state.user_prompt == "Arbitrary transition":
            try:
                target_state.user_prompt = sanitize_prompt(transition_prompt)
            except ValidationError:
                target_state.user_prompt = "Arbitrary transition"

        transition = Transition(
            transition_id=self.transition_repo.count() + 1,
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
        return [
            str(t.transition_id) for t in transitions
        ], f"Transitions for state {state_number} retrieved"

    def get_transition_info(self, transition_id: str) -> tuple[Optional[dict], str]:
        if not is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        try:
            transition_id_int = int(transition_id)
            transition = self.transition_repo.get_by_id(transition_id_int)
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
