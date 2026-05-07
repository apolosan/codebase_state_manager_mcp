import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from ..config import Settings
from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..repositories.sqlite_repository import SQLiteStateRepository
from ..services.branch_detection_service import BranchDetectionService
from ..services.git_manager import GitManager, GitOperationError
from ..services.scc_codec import build_current_state_preview, encode_state_for_llm
from ..utils.audit import get_audit_logger
from ..utils.consistency_checker import ConsistencyChecker
from ..utils.hash import generate_state_hash
from ..utils.ignore_manager import IgnoreManager
from ..utils.init_manager import is_initialized, set_initialized
from ..utils.security import RateLimitExceeded, get_rate_limiter
from ..utils.validation import (
    ValidationError,
    sanitize_prompt,
    validate_reward,
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
    MANAGED_PROJECT_PATH_METADATA_KEY = "managed_project_path"

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
        self._cached_full_hashes_state_number: Optional[int] = None
        self._cached_full_hashes: Optional[Dict[str, str]] = None
        self._ignore_manager = IgnoreManager()
        self._project_path = Path.cwd()
        self._initialized_cache: Optional[bool] = None
        self.branch_detector = BranchDetectionService(git_manager)

    @property
    def audit_logger(self):
        """Lazy initialization of audit logger."""
        if self._audit_logger is None:
            self._audit_logger = get_audit_logger()
        return self._audit_logger

    def _should_run_consistency_check(self) -> bool:
        """Run expensive consistency checks only for the real SQLite-backed service."""
        return isinstance(self.state_repo, SQLiteStateRepository)

    def _is_initialized(self, volume_path: str) -> bool:
        if self._initialized_cache is None:
            self._initialized_cache = is_initialized(volume_path)
        return self._initialized_cache

    def _repair_consistency_for_volume_rebuild(self) -> tuple[bool, Optional[str]]:
        """Repair non-volume consistency issues before rebuilding the snapshot."""
        if not self._should_run_consistency_check():
            return True, None

        checker = ConsistencyChecker(
            state_repo=self.state_repo,
            volume_path=self.settings.docker_volume_name,
            db_path=self.settings.sqlite_path,
        )
        issues = checker.check_all()

        if any(issue.auto_fixable for issue in issues):
            checker.auto_repair()
            issues = checker.check_all()

        blocking_issues = [
            issue.message
            for issue in issues
            if issue.category != "volume" and issue.severity in {"critical", "error"}
        ]
        if blocking_issues:
            return False, "; ".join(blocking_issues)

        self._initialized_cache = is_initialized(self.settings.docker_volume_name)
        return True, None

    def _prepare_volume_root_for_rebuild(
        self, volume_root: Path, codebase_path: Path
    ) -> tuple[bool, Optional[str]]:
        """Ensure the target volume root can receive a rebuilt snapshot."""
        if volume_root.exists() and not volume_root.is_dir():
            return False, f"Volume path exists but is not a directory: {volume_root}"

        volume_root.mkdir(parents=True, exist_ok=True)

        if codebase_path.exists() and not codebase_path.is_dir():
            codebase_path.unlink()

        return True, None

    def _remember_project_path(self, project_path: Path) -> None:
        """Persist the managed project path for later rebuild operations."""
        self._project_path = project_path
        try:
            self.state_repo.set_metadata(
                self.MANAGED_PROJECT_PATH_METADATA_KEY,
                str(project_path),
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to persist managed project path metadata",
                exc_info=True,
            )

    def _iter_candidate_project_paths(self, provided_project_path: Optional[str]) -> list[Path]:
        """Return candidate project roots ordered by trustworthiness."""
        candidates: list[Path] = []

        env_project_path = os.getenv("MANAGED_PROJECT_PATH")
        persisted_project_path = None
        try:
            persisted_project_path = self.state_repo.get_metadata(
                self.MANAGED_PROJECT_PATH_METADATA_KEY
            )
        except Exception:
            persisted_project_path = None

        for raw_path in [
            env_project_path,
            persisted_project_path,
            provided_project_path,
            str(self._project_path),
        ]:
            if not raw_path:
                continue
            candidate = Path(raw_path).expanduser().resolve()
            if candidate.exists() and candidate.is_dir() and candidate not in candidates:
                candidates.append(candidate)

        return candidates

    def _summarize_hash_mismatch(
        self,
        rebuilt_hashes: Dict[str, str],
        expected_hashes: Dict[str, str],
    ) -> str:
        """Build a compact mismatch summary for diagnostics."""
        rebuilt_paths = set(rebuilt_hashes)
        expected_paths = set(expected_hashes)
        missing = sorted(expected_paths - rebuilt_paths)
        extra = sorted(rebuilt_paths - expected_paths)
        changed = sorted(
            path
            for path in rebuilt_paths & expected_paths
            if rebuilt_hashes[path] != expected_hashes[path]
        )
        details = [
            f"missing={len(missing)}",
            f"extra={len(extra)}",
            f"changed={len(changed)}",
        ]
        samples = []
        if missing:
            samples.append(f"missing_sample={missing[:3]}")
        if extra:
            samples.append(f"extra_sample={extra[:3]}")
        if changed:
            samples.append(f"changed_sample={changed[:3]}")
        return ", ".join(details + samples)

    def _create_recovery_transition_for_project(
        self,
        project_path: Path,
        current_state: State,
    ) -> tuple[bool, Optional[State], str]:
        """Create a technical transition so DB state matches the current project."""
        original_project_path = self._project_path
        try:
            self._project_path = project_path
            return self.new_state_transition(
                "Automatic VOLUME_PATH recovery transition to current project snapshot"
            )
        finally:
            self._project_path = original_project_path

    def _get_full_hashes_for_state(self, state_number: int) -> Dict[str, str]:
        """Reconstruct full hashes with a rolling cache for sequential transitions."""
        if state_number < 0:
            return {}

        genesis_state = self.state_repo.get_by_number(0)
        if not genesis_state:
            raise StateNotFoundError("Genesis state not found")

        if state_number == 0:
            genesis_hashes = dict(genesis_state.file_hashes or {})
            self._cached_full_hashes_state_number = 0
            self._cached_full_hashes = dict(genesis_hashes)
            return genesis_hashes

        if (
            self._cached_full_hashes is not None
            and self._cached_full_hashes_state_number is not None
            and self._cached_full_hashes_state_number <= state_number
        ):
            current_hashes = dict(self._cached_full_hashes)
            start_state = self._cached_full_hashes_state_number + 1
        else:
            current_hashes = dict(genesis_state.file_hashes or {})
            start_state = 1

        for current_state_number in range(start_state, state_number + 1):
            state = self.state_repo.get_by_number(current_state_number)
            if state and hasattr(state, "file_hash_deltas") and state.file_hash_deltas:
                for file_path, hash_val in state.file_hash_deltas.items():
                    if hash_val is None:
                        current_hashes.pop(file_path, None)
                    else:
                        current_hashes[file_path] = hash_val

        self._cached_full_hashes_state_number = state_number
        self._cached_full_hashes = dict(current_hashes)
        return current_hashes

    def genesis(
        self,
        project_path: str,
        volume_path: str,
        current_branch: Optional[str] = None,
        current_diff: Optional[str] = None,
    ) -> tuple[bool, Optional[State], str]:
        try:
            source_path = Path(project_path).resolve()
            volume_root = Path(volume_path).resolve()

            if self._is_initialized(str(volume_root)):
                return False, None, "State manager already initialized. Call reset first."

            self._remember_project_path(source_path)
            target_path = volume_root / "codebase"

            # Validate that target_path is not inside source_path to prevent recursion
            if target_path.is_relative_to(source_path):
                return (
                    False,
                    None,
                    (
                        "Volume path must be outside the project path. "
                        f"Got volume_path='{volume_path}' which resolves to "
                        f"'{target_path}' inside project_path='{source_path}'. "
                        "This would cause infinite recursion during file copy."
                    ),
                )

            # Create volume directory
            volume_root.mkdir(parents=True, exist_ok=True)

            # Initialize ignore manager for intelligent filtering
            ignore_manager = self._ignore_manager

            if self.git_manager.is_git_repo(source_path):
                if not self.git_manager.clone_to_volume(source_path, target_path, ignore_manager):
                    return False, None, "Failed to clone repository to volume"
                if not self.git_manager.init_repo(target_path):
                    return False, None, "Failed to initialize git repository in volume"
                branch_name = current_branch or self.git_manager.get_current_branch(
                    repo_path=source_path
                )
                diff_info = current_diff or ""
            else:
                if not self.git_manager.clone_to_volume(source_path, target_path, ignore_manager):
                    return False, None, "Failed to clone files to volume"
                if not self.git_manager.init_repo(target_path):
                    return False, None, "Failed to initialize git repository"
                self.git_manager.create_branch("codebase-state-machine", target_path)
                branch_name = "codebase-state-machine"
                diff_info = ""

            file_hashes = self.git_manager.get_directory_hashes(
                source_path, ignore_manager=ignore_manager
            )
            compact_payload = encode_state_for_llm(
                state_repo=self.state_repo,
                git_diff_info=diff_info,
                file_hashes=file_hashes,
            )

            state_0 = State(
                state_number=0,
                user_prompt="Genesis state - State machine initialized",
                branch_name=branch_name,
                git_diff_info=diff_info,
                hash="",
                file_hashes=file_hashes,
                file_hash_deltas={
                    k: v for k, v in file_hashes.items()
                },  # Genesis stores full hashes as deltas too
                llm_context=str(compact_payload["llm_context"]),
                compression_version=str(compact_payload["compression_version"]),
                compacted_at=compact_payload["compacted_at"],
            )
            state_0.hash = generate_state_hash(
                state_0.user_prompt,
                state_0.branch_name,
                state_0.git_diff_info,
                state_0.state_number,
            )

            if not self.state_repo.create(state_0):
                return False, None, "Failed to save genesis state"

            if not self.state_repo.set_current(0):
                return False, state_0, "Failed to set current state to genesis state"

            resolved_volume_path = str(volume_root)
            self.settings.docker_volume_name = resolved_volume_path
            self.settings.volume_path = resolved_volume_path

            if not set_initialized(resolved_volume_path, True):
                return False, None, "Failed to set initialized flag"

            self._initialized_cache = True

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
        file_hashes: Optional[dict],
        file_hash_deltas: dict,
        project_path: Path,
        current_branch_name: Optional[str] = None,
        reward: float | None = None,
        llm_context: str | None = None,
        compression_version: str | None = None,
        compacted_at=None,
    ) -> tuple[bool, Optional[State], str]:
        """Create a new state and transition atomically.

        This method ensures atomicity by:
        1. Creating the new state
        2. Creating the transition record
        3. Updating the current state pointer
        4. Rolling back the state if pointer update fails

        Returns:
            (success, new_state, message)
        """
        try:
            sanitized_prompt = sanitize_prompt(user_prompt)
        except ValidationError as e:
            return False, None, f"Invalid prompt: {e}"

        try:
            validated_reward = validate_reward(reward)
        except ValidationError as e:
            return False, None, f"Invalid reward: {e}"

        # CORREÇÃO CRÍTICA: Capturar branch atual do filesystem, não do estado anterior
        resolved_branch_name = current_branch_name or self.branch_detector.get_current_branch_name(
            project_path
        )

        # Log de mudança de branch (útil para debugging)
        if resolved_branch_name != current_state.branch_name:
            logging.info(
                f"Branch changed from '{current_state.branch_name}' to "
                f"'{resolved_branch_name}' during state transition"
            )

        # Create new state with placeholder number (will be assigned by create_next)
        new_state = State(
            state_number=0,  # Placeholder, will be replaced by create_next
            user_prompt=sanitized_prompt,
            branch_name=resolved_branch_name,
            git_diff_info=diff_info,
            hash="",  # Will be generated by create_next
            file_hashes=file_hashes,
            file_hash_deltas=file_hash_deltas,  # Store only deltas
            llm_context=llm_context,
            compression_version=compression_version,
            compacted_at=compacted_at,
        )

        try:
            # Step 1: Create the new state
            if not self.state_repo.create_next(new_state):
                return False, None, "Failed to create new state in database"

            # Step 2: Create the transition record
            transition = Transition(
                transition_id=0,  # Placeholder, will be assigned by create_next
                current_state=current_state.state_number,
                next_state=new_state.state_number,
                user_prompt=sanitized_prompt,
                reward=validated_reward,
            )
            if not self.transition_repo.create_next(transition):
                # Rollback: delete the created state
                logging.error(
                    f"Failed to create transition record. Rolling back state {new_state.state_number}"
                )
                self.state_repo.delete(new_state.state_number)
                return False, None, "Failed to create transition, state rolled back"

            # Step 3: Update current state pointer (critical for consistency)
            if not self.state_repo.set_current(new_state.state_number):
                # Rollback: delete both transition and state
                logging.error(
                    f"Failed to update current state pointer to {new_state.state_number}. "
                    f"Rolling back state and transition"
                )
                try:
                    if not self.transition_repo.delete(transition.transition_id):
                        logging.error(
                            "Failed to delete orphan transition %s during rollback",
                            transition.transition_id,
                        )
                except Exception as rollback_error:
                    logging.error(
                        "Rollback failed while deleting transition %s: %s",
                        transition.transition_id,
                        rollback_error,
                    )
                self.state_repo.delete(new_state.state_number)
                return (
                    False,
                    None,
                    (
                        "Failed to update current state pointer. "
                        "This may indicate database lock contention or corruption. "
                        "State creation rolled back."
                    ),
                )

            return True, new_state, f"Transition to state {new_state.state_number} successful"
        except Exception as e:
            return False, None, f"Atomic operation failed: {e}"

    def new_state_transition(
        self, user_prompt: str, reward: float | None = None
    ) -> tuple[bool, Optional[State], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        if self._should_run_consistency_check():
            checker = ConsistencyChecker(
                state_repo=self.state_repo,
                volume_path=self.settings.docker_volume_name,
                db_path=self.settings.sqlite_path,
            )
            issues = checker.check_all()

            if issues:
                logging.warning(f"Consistency issues detected: {len(issues)} issue(s)")
                for issue in issues:
                    logging.warning(f"  - {issue.severity.upper()}: {issue.message}")

                auto_fixable = [i for i in issues if i.auto_fixable]
                if auto_fixable:
                    logging.info(f"Attempting auto-repair for {len(auto_fixable)} issue(s)...")
                    repair_results = checker.auto_repair()

                    for issue_msg, success in repair_results.items():
                        if success:
                            logging.info(f"  ✓ Fixed: {issue_msg}")
                        else:
                            logging.error(f"  ✗ Failed to fix: {issue_msg}")

                    remaining_issues = checker.check_all()
                    if remaining_issues:
                        critical = [i for i in remaining_issues if i.severity == "critical"]
                        if critical:
                            error_msgs = "; ".join([i.message for i in critical])
                            return False, None, f"Critical consistency issues remain: {error_msgs}"

        current_state = self.state_repo.get_current()
        if not current_state:
            return False, None, "No current state found. Call genesis first."

        project_path = self._project_path

        # Create ignore manager to respect .gitignore patterns
        ignore_manager = self._ignore_manager

        volume_codebase_path: Optional[Path] = None
        if self._should_run_consistency_check():
            candidate_volume_codebase = Path(self.settings.docker_volume_name) / "codebase"
            if candidate_volume_codebase.exists():
                volume_codebase_path = candidate_volume_codebase

        if self._should_run_consistency_check():
            current_branch_name = self.branch_detector.get_current_branch_name(project_path)
        else:
            current_branch_name = current_state.branch_name

        # Reconstruct complete file hashes for the CURRENT state so the next transition
        # stores only the delta between the real current snapshot and the project now.
        try:
            last_hashes = self._get_current_full_hashes(current_state)
        except StateNotFoundError as e:
            # Fallback: if genesis reconstruction fails, try to get from volume
            if volume_codebase_path is not None:
                last_hashes = self.git_manager.get_directory_hashes(
                    volume_codebase_path, ignore_manager=ignore_manager
                )
            else:
                last_hashes = {}
        diff_info, delta_hashes = self.git_manager.compute_changes_since_last_state(
            project_path=project_path,
            last_state_file_hashes=last_hashes,
            volume_codebase_path=volume_codebase_path,
            is_genesis=False,  # Transitions are not genesis
            ignore_manager=ignore_manager,
        )
        compact_hashes = {
            file_path: hash_value
            for file_path, hash_value in delta_hashes.items()
            if hash_value is not None
        }
        compact_payload = encode_state_for_llm(
            state_repo=self.state_repo,
            git_diff_info=diff_info,
            file_hashes=compact_hashes,
        )

        # For delta storage optimization: store only deltas for transition states
        # Don't reconstruct full hashes here - store deltas only
        success, new_state, message = self._create_state_and_transition_atomic(
            user_prompt,
            diff_info,
            current_state,
            None,  # No full hashes for transition states (save space)
            delta_hashes,  # Store actual deltas for optimization
            project_path,  # NOVO: Passar project_path
            current_branch_name=current_branch_name,
            reward=reward,
            llm_context=str(compact_payload["llm_context"]),
            compression_version=str(compact_payload["compression_version"]),
            compacted_at=compact_payload["compacted_at"],
        )

        # Note: set_current() is now called inside _create_state_and_transition_atomic()
        # for true atomicity. If the method returns success=True, current is already set.

        if success and new_state:
            try:
                if volume_codebase_path is not None:
                    self.git_manager.sync_project_to_volume(
                        source_path=project_path,
                        volume_path=volume_codebase_path,
                        sync_git=True,
                        ignore_manager=ignore_manager,
                    )
            except (GitOperationError, OSError) as e:
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
            transition_id=0,  # Placeholder, will be assigned by create_next
            current_state=current_state.state_number,
            next_state=target_state.state_number,
            user_prompt=transition_prompt,
        )
        if not self.transition_repo.create_next(transition):
            return False, None, "Failed to create transition"

        if not self.state_repo.set_current(target_state.state_number):
            return (
                False,
                self._ensure_compact_state_context(target_state),
                "Transition created but failed to update current state pointer",
            )

        return (
            True,
            self._ensure_compact_state_context(target_state),
            f"Arbitrary transition to state {next_state} successful",
        )

    def fix_volume_path(
        self, project_path: Optional[str] = None
    ) -> tuple[bool, Optional[dict], str]:
        """Repair the configured volume snapshot and finalize DB state when needed."""
        consistency_ok, consistency_message = self._repair_consistency_for_volume_rebuild()
        if not consistency_ok:
            return (
                False,
                None,
                f"Cannot rebuild volume path while consistency issues remain: {consistency_message}",
            )

        current_state = self.state_repo.get_current()
        if not current_state:
            return (
                False,
                None,
                "No current state found. Cannot rebuild volume path without DB context.",
            )

        volume_root = Path(self.settings.docker_volume_name)
        codebase_path = volume_root / "codebase"
        ignore_manager = self._ignore_manager
        candidate_paths = self._iter_candidate_project_paths(project_path)
        if not candidate_paths:
            return (
                False,
                None,
                "No valid project path available for rebuild. Set MANAGED_PROJECT_PATH or run genesis from the managed codebase.",
            )

        try:
            prepared, prepare_message = self._prepare_volume_root_for_rebuild(
                volume_root=volume_root,
                codebase_path=codebase_path,
            )
            if not prepared:
                return False, None, str(prepare_message)
            recovery_transition_created = False
            used_source_path: Optional[Path] = None
            current_project_hashes: Optional[Dict[str, str]] = None
            last_mismatch_summary: Optional[str] = None

            for candidate_path in candidate_paths:
                used_source_path = candidate_path
                current_project_hashes = self.git_manager.get_directory_hashes(
                    candidate_path, ignore_manager=ignore_manager
                )
                expected_hashes = self._get_current_full_hashes(current_state)

                if current_project_hashes == expected_hashes:
                    self._remember_project_path(candidate_path)
                    break

                last_mismatch_summary = self._summarize_hash_mismatch(
                    rebuilt_hashes=current_project_hashes,
                    expected_hashes=expected_hashes,
                )
            else:
                if used_source_path is None or current_project_hashes is None:
                    return False, None, "Failed to inspect project snapshot for recovery"

                created, created_state, creation_message = (
                    self._create_recovery_transition_for_project(
                        project_path=used_source_path,
                        current_state=current_state,
                    )
                )
                if not created or created_state is None:
                    return (
                        False,
                        None,
                        "Project snapshot diverges from the current state stored in the database"
                        + (f" ({last_mismatch_summary})" if last_mismatch_summary else "")
                        + f"; failed to create recovery transition: {creation_message}",
                    )

                current_state = created_state
                recovery_transition_created = True
                self._remember_project_path(used_source_path)

            if used_source_path is None:
                return False, None, "No project path selected for recovery"

            if not self.git_manager.clone_to_volume(
                used_source_path, codebase_path, ignore_manager
            ):
                return False, None, "Failed to rebuild codebase snapshot in volume"

            rebuilt_hashes = self.git_manager.get_directory_hashes(
                codebase_path, ignore_manager=ignore_manager
            )
            expected_hashes = self._get_current_full_hashes(current_state)
            if rebuilt_hashes != expected_hashes:
                mismatch_summary = self._summarize_hash_mismatch(
                    rebuilt_hashes=rebuilt_hashes,
                    expected_hashes=expected_hashes,
                )
                shutil.rmtree(codebase_path, ignore_errors=True)
                return (
                    False,
                    None,
                    "Recovered state still does not match rebuilt volume snapshot"
                    + (f" ({mismatch_summary})" if mismatch_summary else ""),
                )

            if not set_initialized(str(volume_root), True):
                shutil.rmtree(codebase_path, ignore_errors=True)
                return False, None, "Failed to restore initialized flag for rebuilt volume"

            self._initialized_cache = True

            if self._should_run_consistency_check():
                checker = ConsistencyChecker(
                    state_repo=self.state_repo,
                    volume_path=self.settings.docker_volume_name,
                    db_path=self.settings.sqlite_path,
                )
                remaining_issues = checker.check_all()
                blocking_issues = [
                    issue.message
                    for issue in remaining_issues
                    if issue.severity in {"critical", "error"}
                ]
                if blocking_issues:
                    shutil.rmtree(codebase_path, ignore_errors=True)
                    self._initialized_cache = False
                    return (
                        False,
                        None,
                        "Recovery transition completed but consistency issues remain: "
                        + "; ".join(blocking_issues),
                    )

            return (
                True,
                {
                    "volume_path": str(volume_root),
                    "codebase_path": str(codebase_path),
                    "current_state": current_state.state_number,
                    "recovery_transition_created": recovery_transition_created,
                },
                "Volume path recovered successfully",
            )
        except StateNotFoundError:
            return False, None, "Genesis state not found. Cannot validate rebuilt volume."
        except (GitOperationError, OSError, ValueError) as e:
            return False, None, f"Failed to rebuild volume path: {e}"

    def get_current_state(self) -> tuple[Optional[State], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_current()
        if state:
            return self._ensure_compact_state_context(state), "Current state retrieved"
        return None, "No state found"

    def get_current_state_number(self) -> tuple[Optional[int], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_current()
        if state:
            return state.state_number, "Current state number retrieved"
        return None, "No state found"

    def get_state_info(self, state_number: int) -> tuple[Optional[State], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        state = self.state_repo.get_by_number(state_number)
        if state:
            return self._ensure_compact_state_context(state), f"State {state_number} info retrieved"
        return None, f"State {state_number} not found"

    def _get_generation_reward_by_state(self) -> dict[int, float | None]:
        total_transitions = self.transition_repo.count()
        if total_transitions <= 0:
            return {}

        rewards_by_state: dict[int, float | None] = {}
        transitions = self.transition_repo.get_last(total_transitions)
        for transition in sorted(transitions, key=lambda item: int(item.transition_id)):
            rewards_by_state.setdefault(transition.next_state, transition.reward)
        return rewards_by_state

    def _compact_state_payload_with_reward(
        self,
        state: State,
        generation_rewards: dict[int, float | None],
    ) -> dict[str, object]:
        compact_state = self._ensure_compact_state_context(state)
        raw_payload = compact_state.to_dict()
        payload: dict[str, object] = {
            "state_number": raw_payload.get("state_number"),
            "llm_context": raw_payload.get("llm_context"),
            "compression_version": raw_payload.get("compression_version"),
            "compacted_at": raw_payload.get("compacted_at"),
        }
        reward = generation_rewards.get(compact_state.state_number)
        if reward is not None:
            payload["reward"] = reward
        return payload

    def get_compact_states(
        self,
        state: int | None = None,
        start_state: int | None = None,
        end_state: int | None = None,
    ) -> tuple[bool, list[dict[str, object]], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return False, [], "State manager not initialized. Call genesis first."

        has_single_state = state is not None
        has_range_state = start_state is not None or end_state is not None
        if has_single_state and has_range_state:
            return (
                False,
                [],
                "Invalid selector: provide exactly one selector mode (state or start_state + end_state)",
            )
        if (start_state is None) != (end_state is None):
            return (
                False,
                [],
                "Invalid selector: start_state and end_state must be provided together",
            )

        selected_states: list[State]
        if state is not None:
            if state < 0:
                return False, [], "Invalid selector: state must be non-negative"
            state_obj = self.state_repo.get_by_number(state)
            if state_obj is None:
                return False, [], f"State {state} not found"
            selected_states = [state_obj]
            message = f"Compact state {state} retrieved"
        elif start_state is not None and end_state is not None:
            if start_state < 0 or end_state < 0:
                return False, [], "Invalid selector: state range must be non-negative"
            if start_state > end_state:
                return (
                    False,
                    [],
                    "Invalid selector: start_state cannot be greater than end_state",
                )
            all_states = self.state_repo.get_all()
            selected_states = [
                candidate
                for candidate in all_states
                if start_state <= candidate.state_number <= end_state
            ]
            found_numbers = {candidate.state_number for candidate in selected_states}
            missing_states = [
                state_number
                for state_number in range(start_state, end_state + 1)
                if state_number not in found_numbers
            ]
            if missing_states:
                return (
                    False,
                    [],
                    f"State range {start_state}-{end_state} contains missing states: {missing_states}",
                )
            message = f"Compact states {start_state}-{end_state} retrieved"
        else:
            selected_states = self.state_repo.get_all()
            message = f"All compact states retrieved: {len(selected_states)} total"

        generation_rewards = self._get_generation_reward_by_state()
        compact_states = [
            self._compact_state_payload_with_reward(selected_state, generation_rewards)
            for selected_state in selected_states
        ]
        return True, compact_states, message

    def total_states(self) -> tuple[int, str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return 0, "State manager not initialized. Call genesis first."
        return self.state_repo.count(), "Total states count retrieved"

    def search_states(self, text: str) -> tuple[list[int], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        results = self.state_repo.search(text)
        return results, f"Found {len(results)} states matching '{text}'"

    def get_current_state_compact_context(
        self, include_vocabulary: bool = False
    ) -> tuple[Optional[dict[str, object]], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."

        current_state = self.state_repo.get_current()
        if not current_state:
            return None, "No current state found. Call genesis first."

        ignore_manager = self._ignore_manager
        project_path = self._project_path
        volume_codebase_path = Path(self.settings.docker_volume_name) / "codebase"
        if not volume_codebase_path.exists():
            volume_codebase_path = None  # type: ignore[assignment]

        try:
            last_hashes = self._get_current_full_hashes(current_state)
        except StateNotFoundError:
            last_hashes = {}

        diff_info, delta_hashes = self.git_manager.compute_changes_since_last_state(
            project_path=project_path,
            last_state_file_hashes=last_hashes,
            volume_codebase_path=volume_codebase_path,
            is_genesis=False,
            ignore_manager=ignore_manager,
        )
        compact_hashes = {
            file_path: hash_value
            for file_path, hash_value in delta_hashes.items()
            if hash_value is not None
        }
        preview = build_current_state_preview(
            state_repo=self.state_repo,
            git_diff_info=diff_info,
            file_hashes=compact_hashes,
            include_vocabulary=include_vocabulary,
        )
        return {
            "current_state": current_state.state_number,
            "preview": preview,
        }, "Current workspace compact context generated"

    def _ensure_compact_state_context(self, state: State) -> State:
        if state.llm_context and state.compression_version and state.compacted_at:
            return state

        available_hashes = dict(state.file_hashes or {})
        if not available_hashes:
            available_hashes = {
                file_path: hash_value
                for file_path, hash_value in state.file_hash_deltas.items()
                if hash_value is not None
            }

        compact_payload = encode_state_for_llm(
            state_repo=self.state_repo,
            git_diff_info=state.git_diff_info,
            file_hashes=available_hashes,
        )
        state.llm_context = str(compact_payload["llm_context"])
        state.compression_version = str(compact_payload["compression_version"])
        state.compacted_at = compact_payload["compacted_at"]
        return state

    def _transition_payload(
        self, transition: Transition, state_number: Optional[int] = None
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "transition_id": str(transition.transition_id),
            "source_state": transition.current_state,
            "destination_state": transition.next_state,
            "user_prompt": transition.user_prompt,
            "timestamp": transition.timestamp.isoformat() if transition.timestamp else None,
            "reward": transition.reward,
        }
        if state_number is not None:
            payload["role"] = (
                "source" if transition.current_state == state_number else "destination"
            )
        return payload

    def get_state_transitions(self, state_number: int) -> tuple[list, str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        transitions = self.transition_repo.get_by_state(state_number)
        result = [self._transition_payload(transition, state_number) for transition in transitions]
        return result, f"Transitions for state {state_number} retrieved: {len(result)} total"

    def get_transition_info(self, transition_id: str) -> tuple[Optional[dict], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return None, "State manager not initialized. Call genesis first."
        try:
            transition_id_int = int(transition_id)
            transition = self.transition_repo.get_by_id(transition_id_int)
            if transition:
                return transition.to_dict(), f"Transition {transition_id} info retrieved"
            return None, f"Transition {transition_id} not found"
        except ValueError:
            return None, f"Invalid transition ID format: {transition_id}"

    def _reconstruct_file_hashes(
        self, from_state: int, deltas: Dict[str, Optional[str]]
    ) -> Dict[str, str]:
        """Reconstruct full file hashes from genesis state by applying deltas sequentially."""
        current_hashes = self._get_full_hashes_for_state(from_state)
        return current_hashes

    def _get_current_full_hashes(self, current_state: State) -> Dict[str, str]:
        """Get complete file hashes for the current state by reconstructing from genesis + all deltas."""
        # If current state has full hashes (genesis state), use them directly
        if current_state.state_number == 0 and current_state.file_hashes:
            return dict(current_state.file_hashes)

        return self._get_full_hashes_for_state(current_state.state_number)

    def get_rewarded_transitions(self) -> tuple[list[dict[str, object]], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        transitions = self.transition_repo.get_rewarded()
        result = [self._transition_payload(transition) for transition in transitions]
        return result, f"Rewarded transitions retrieved: {len(result)} total"

    def set_transition_reward(
        self,
        reward: float | None,
        transition_id: int | None = None,
        current_state: int | None = None,
        next_state: int | None = None,
    ) -> tuple[bool, Optional[dict[str, object]], str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return False, None, "State manager not initialized. Call genesis first."

        try:
            validated_reward = validate_reward(reward)
        except ValidationError as e:
            return False, None, f"Invalid reward: {e}"

        has_transition_id = transition_id is not None
        has_any_pair_value = current_state is not None or next_state is not None
        has_full_pair = current_state is not None and next_state is not None

        if has_transition_id == has_any_pair_value:
            return (
                False,
                None,
                "Invalid selector: provide exactly one selector mode (transition_id or current_state + next_state)",
            )

        if not has_transition_id and not has_full_pair:
            return (
                False,
                None,
                "Invalid selector: current_state and next_state must be provided together",
            )

        if transition_id is not None:
            transition = self.transition_repo.get_by_id(transition_id)
            if transition is None:
                return False, None, f"Transition {transition_id} not found"
        else:
            matches = self.transition_repo.get_by_state_pair(current_state or 0, next_state or 0)
            if not matches:
                return (
                    False,
                    None,
                    f"No transition found for pair ({current_state}, {next_state})",
                )
            if len(matches) > 1:
                return (
                    False,
                    None,
                    "Ambiguous transition selector: multiple transitions match the state pair; use transition_id",
                )
            transition = matches[0]

        previous_reward = transition.reward
        if not self.transition_repo.update_reward(transition.transition_id, validated_reward):
            return False, None, "Failed to update transition reward"

        updated_transition = self.transition_repo.get_by_id(transition.transition_id)
        if updated_transition is None:
            return False, None, "Transition reward updated but transition could not be reloaded"

        payload = self._transition_payload(updated_transition)
        payload["previous_reward"] = previous_reward
        return True, payload, "Transition reward updated"

    def track_transitions(self) -> tuple[list, str]:
        if not self._is_initialized(self.settings.docker_volume_name):
            return [], "State manager not initialized. Call genesis first."
        transitions = self.transition_repo.get_last(5)
        return [str(t.transition_id) for t in transitions], "Last 5 transitions retrieved"
