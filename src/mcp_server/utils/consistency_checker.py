"""Consistency checker and auto-repair for codebase state manager.

This module provides tools to diagnose and fix inconsistencies between:
- Database state vs. initialization flag
- Current state pointer vs. actual states
- Volume path existence vs. initialization flag
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConsistencyIssue:
    """Represents a consistency issue found in the system."""

    def __init__(
        self,
        severity: str,  # "warning", "error", "critical"
        category: str,  # "db", "filesystem", "state_pointer", "volume"
        message: str,
        auto_fixable: bool = False,
        fix_action: Optional[str] = None,
    ):
        self.severity = severity
        self.category = category
        self.message = message
        self.auto_fixable = auto_fixable
        self.fix_action = fix_action

    def __repr__(self) -> str:
        fixable = " [AUTO-FIXABLE]" if self.auto_fixable else ""
        return f"[{self.severity.upper()}] {self.category}: {self.message}{fixable}"


class ConsistencyChecker:
    """Check and repair system consistency issues."""

    def __init__(self, state_repo, volume_path: str, db_path: str):
        """Initialize consistency checker.

        Args:
            state_repo: StateRepository instance
            volume_path: Path to volume directory (e.g., /tmp/radoc_branches)
            db_path: Path to SQLite database file
        """
        self.state_repo = state_repo
        self.volume_path = Path(volume_path)
        self.db_path = Path(db_path)
        self.issues: List[ConsistencyIssue] = []

    def check_all(self) -> List[ConsistencyIssue]:
        """Run all consistency checks.

        Returns:
            List of ConsistencyIssue objects found.
        """
        self.issues = []

        self._check_initialization_flag()
        self._check_database_accessible()
        self._check_volume_path()
        self._check_current_state_pointer()
        self._check_state_sequence()

        return self.issues

    def _check_initialization_flag(self):
        """Check if initialization flag exists and is consistent with DB."""
        from ..utils.init_manager import INITIALIZED_FLAG, is_initialized

        flag_path = self.volume_path / INITIALIZED_FLAG
        flag_exists = flag_path.exists()
        volume_exists = self.volume_path.exists()

        if not volume_exists:
            self.issues.append(
                ConsistencyIssue(
                    severity="critical",
                    category="volume",
                    message=f"Volume path does not exist: {self.volume_path}",
                    auto_fixable=False,
                )
            )
            return

        # Check if DB has states but flag is missing
        try:
            state_count = self.state_repo.count()
            if state_count > 0 and not flag_exists:
                self.issues.append(
                    ConsistencyIssue(
                        severity="error",
                        category="filesystem",
                        message=(
                            f"Database has {state_count} states but initialization flag "
                            f"is missing at {flag_path}"
                        ),
                        auto_fixable=True,
                        fix_action="recreate_flag",
                    )
                )
        except Exception as e:
            self.issues.append(
                ConsistencyIssue(
                    severity="error",
                    category="db",
                    message=f"Cannot query database: {e}",
                    auto_fixable=False,
                )
            )

    def _check_database_accessible(self):
        """Check if database file exists and is accessible."""
        if not self.db_path.exists():
            self.issues.append(
                ConsistencyIssue(
                    severity="critical",
                    category="db",
                    message=f"Database file does not exist: {self.db_path}",
                    auto_fixable=False,
                )
            )
            return

        # Try to query the database
        try:
            self.state_repo.count()
        except Exception as e:
            self.issues.append(
                ConsistencyIssue(
                    severity="critical",
                    category="db",
                    message=f"Database is not accessible or corrupted: {e}",
                    auto_fixable=False,
                )
            )

    def _check_volume_path(self):
        """Check volume path exists and contains expected structure."""
        if not self.volume_path.exists():
            self.issues.append(
                ConsistencyIssue(
                    severity="critical",
                    category="volume",
                    message=f"Volume path does not exist: {self.volume_path}",
                    auto_fixable=False,
                )
            )
            return

        codebase_path = self.volume_path / "codebase"
        if not codebase_path.exists():
            self.issues.append(
                ConsistencyIssue(
                    severity="warning",
                    category="volume",
                    message=f"Codebase subdirectory missing: {codebase_path}",
                    auto_fixable=False,
                )
            )

    def _check_current_state_pointer(self):
        """Check if current state pointer is valid."""
        try:
            current_state = self.state_repo.get_current()
            if current_state is None:
                state_count = self.state_repo.count()
                if state_count > 0:
                    self.issues.append(
                        ConsistencyIssue(
                            severity="error",
                            category="state_pointer",
                            message=(
                                f"No current state pointer but {state_count} states exist. "
                                f"Current state metadata may be corrupted."
                            ),
                            auto_fixable=True,
                            fix_action="reset_current_to_latest",
                        )
                    )
        except Exception as e:
            self.issues.append(
                ConsistencyIssue(
                    severity="error",
                    category="state_pointer",
                    message=f"Error reading current state: {e}",
                    auto_fixable=False,
                )
            )

    def _check_state_sequence(self):
        """Check if state numbers are sequential without gaps."""
        try:
            all_states = self.state_repo.get_all()
            if not all_states:
                return

            state_numbers = [s.state_number for s in all_states]
            state_numbers.sort()

            # Check for gaps
            expected_sequence = list(range(state_numbers[0], state_numbers[-1] + 1))
            missing = set(expected_sequence) - set(state_numbers)

            if missing:
                self.issues.append(
                    ConsistencyIssue(
                        severity="warning",
                        category="db",
                        message=f"Missing state numbers in sequence: {sorted(missing)}",
                        auto_fixable=False,
                    )
                )

            # Check if genesis state exists
            if 0 not in state_numbers:
                self.issues.append(
                    ConsistencyIssue(
                        severity="critical",
                        category="db",
                        message="Genesis state (state 0) is missing from database",
                        auto_fixable=False,
                    )
                )
        except Exception as e:
            self.issues.append(
                ConsistencyIssue(
                    severity="error",
                    category="db",
                    message=f"Error checking state sequence: {e}",
                    auto_fixable=False,
                )
            )

    def auto_repair(self) -> Dict[str, bool]:
        """Attempt to automatically fix auto-fixable issues.

        Returns:
            Dict mapping issue message to fix success (True/False).
        """
        results = {}

        for issue in self.issues:
            if not issue.auto_fixable:
                continue

            try:
                if issue.fix_action == "recreate_flag":
                    success = self._fix_recreate_flag()
                    results[issue.message] = success
                    if success:
                        logger.info(f"Fixed: {issue.message}")
                    else:
                        logger.error(f"Failed to fix: {issue.message}")

                elif issue.fix_action == "reset_current_to_latest":
                    success = self._fix_reset_current_to_latest()
                    results[issue.message] = success
                    if success:
                        logger.info(f"Fixed: {issue.message}")
                    else:
                        logger.error(f"Failed to fix: {issue.message}")

            except Exception as e:
                logger.error(f"Error attempting to fix '{issue.message}': {e}")
                results[issue.message] = False

        return results

    def _fix_recreate_flag(self) -> bool:
        """Recreate the initialization flag."""
        from ..utils.init_manager import set_initialized

        try:
            return set_initialized(str(self.volume_path), True)
        except Exception as e:
            logger.error(f"Failed to recreate initialization flag: {e}")
            return False

    def _fix_reset_current_to_latest(self) -> bool:
        """Reset current state pointer to the latest state."""
        try:
            all_states = self.state_repo.get_all()
            if not all_states:
                return False

            latest_state = max(all_states, key=lambda s: s.state_number)
            success = self.state_repo.set_current(latest_state.state_number)

            if success:
                logger.info(f"Reset current state pointer to state {latest_state.state_number}")
            return bool(success)
        except Exception as e:
            logger.error(f"Failed to reset current state pointer: {e}")
            return False

    def get_summary(self) -> str:
        """Get a human-readable summary of all issues found.

        Returns:
            Formatted string with issue summary.
        """
        if not self.issues:
            return "✓ No consistency issues found."

        critical = [i for i in self.issues if i.severity == "critical"]
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]

        lines = [
            f"\n{'='*60}",
            "CONSISTENCY CHECK REPORT",
            f"{'='*60}",
            f"Total issues: {len(self.issues)}",
            f"  Critical: {len(critical)}",
            f"  Errors: {len(errors)}",
            f"  Warnings: {len(warnings)}",
            f"{'='*60}",
        ]

        for issue in critical:
            lines.append(f"\n{issue}")
        for issue in errors:
            lines.append(f"\n{issue}")
        for issue in warnings:
            lines.append(f"\n{issue}")

        auto_fixable_count = len([i for i in self.issues if i.auto_fixable])
        if auto_fixable_count > 0:
            lines.append(f"\n{'-'*60}")
            lines.append(f"{auto_fixable_count} issue(s) can be auto-repaired.")
            lines.append("Run auto_repair() to attempt fixes.")

        return "\n".join(lines)
