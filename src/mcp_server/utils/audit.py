"""Audit logging module for Codebase State Manager.

Provides comprehensive audit trail for security-sensitive operations.
Records all state transitions, configuration changes, and access events.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    """Types of audit events."""

    STATE_TRANSITION = "STATE_TRANSITION"
    ARBITRARY_TRANSITION = "ARBITRARY_TRANSITION"
    GENESIS = "GENESIS"
    STATE_ACCESS = "STATE_ACCESS"
    SEARCH = "SEARCH"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    INITIALIZATION = "INITIALIZATION"
    ERROR = "ERROR"


class AuditOutcome(str, Enum):
    """Outcome of an audited operation."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


@dataclass
class AuditEvent:
    """Represents a single audit event."""

    event_type: AuditEventType
    outcome: AuditOutcome
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    client_id: str = "system"
    session_id: str | None = None
    state_number: int | None = None
    previous_state: int | None = None
    target_state: int | None = None
    operation: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary."""
        return {
            "event_type": (
                self.event_type.value
                if isinstance(self.event_type, AuditEventType)
                else self.event_type
            ),
            "outcome": (
                self.outcome.value if isinstance(self.outcome, AuditOutcome) else self.outcome
            ),
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "session_id": self.session_id,
            "state_number": self.state_number,
            "previous_state": self.previous_state,
            "target_state": self.target_state,
            "operation": self.operation,
            "details": self.details,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class AuditLogger:
    """Thread-safe audit logger for comprehensive event tracking."""

    EVENT_TYPES_TO_LOG = {
        AuditEventType.STATE_TRANSITION,
        AuditEventType.ARBITRARY_TRANSITION,
        AuditEventType.GENESIS,
        AuditEventType.SECURITY_VIOLATION,
        AuditEventType.RATE_LIMIT_EXCEEDED,
        AuditEventType.VALIDATION_FAILURE,
    }

    def __init__(
        self,
        logger: logging.Logger | None = None,
        min_level: int = logging.INFO,
        include_metadata: bool = True,
    ) -> None:
        self._logger = logger or logging.getLogger("audit")
        self._min_level = min_level
        self._include_metadata = include_metadata
        self._events_buffer: list[AuditEvent] = []
        self._buffer_lock = threading.Lock()
        self._buffer_max_size = 1000
        self._enabled = True

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        Args:
            event: Audit event to log
        """
        if not self._enabled:
            return

        if event.event_type not in self.EVENT_TYPES_TO_LOG:
            return

        with self._buffer_lock:
            self._events_buffer.append(event)
            if len(self._events_buffer) >= self._buffer_max_size:
                self._flush_buffer()

        event_dict = event.to_dict()

        level = self._get_level_for_outcome(event.outcome)
        self._logger.log(
            level,
            f"AUDIT: {event.event_type.value if hasattr(event.event_type, 'value') else event.event_type} - {event.operation}",
            extra={"audit_event": event_dict, "extra_data": event_dict},
        )

    def log_state_transition(
        self,
        from_state: int,
        to_state: int,
        success: bool,
        prompt: str | None = None,
        client_id: str = "system",
        session_id: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a state transition event.

        Args:
            from_state: Source state number
            to_state: Target state number
            success: Whether the transition succeeded
            prompt: User prompt associated with transition
            client_id: Client identifier
            session_id: Session identifier
            duration_ms: Operation duration in milliseconds
            error_message: Error message if failed
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.STATE_TRANSITION,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            previous_state=from_state,
            target_state=to_state,
            operation=f"state_transition: {from_state} -> {to_state}",
            client_id=client_id,
            session_id=session_id,
            duration_ms=duration_ms,
            error_message=error_message,
            details={"prompt_length": len(prompt) if prompt else 0},
            metadata=metadata or {},
        )
        self.log_event(event)

    def log_arbitrary_transition(
        self,
        from_state: int,
        to_state: int,
        success: bool,
        client_id: str = "system",
        session_id: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an arbitrary state transition event.

        Args:
            from_state: Source state number
            to_state: Target state number
            success: Whether the transition succeeded
            client_id: Client identifier
            session_id: Session identifier
            duration_ms: Operation duration in milliseconds
            error_message: Error message if failed
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.ARBITRARY_TRANSITION,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            previous_state=from_state,
            target_state=to_state,
            operation=f"arbitrary_transition: {from_state} -> {to_state}",
            client_id=client_id,
            session_id=session_id,
            duration_ms=duration_ms,
            error_message=error_message,
            metadata=metadata or {},
        )
        self.log_event(event)

    def log_genesis(
        self,
        success: bool,
        project_path: str | None = None,
        client_id: str = "system",
        session_id: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a genesis initialization event.

        Args:
            success: Whether genesis succeeded
            project_path: Path to the project
            client_id: Client identifier
            session_id: Session identifier
            duration_ms: Operation duration in milliseconds
            error_message: Error message if failed
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.GENESIS,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            operation="genesis",
            client_id=client_id,
            session_id=session_id,
            duration_ms=duration_ms,
            error_message=error_message,
            details={"project_path": project_path} if project_path else {},
            metadata=metadata or {},
        )
        self.log_event(event)

    def log_security_violation(
        self,
        violation_type: str,
        details: dict[str, Any],
        client_id: str = "unknown",
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a security violation event.

        Args:
            violation_type: Type of violation (e.g., "CWE-78", "CWE-22")
            details: Details of the violation
            client_id: Client identifier
            session_id: Session identifier
            ip_address: Client IP address
            user_agent: Client user agent
        """
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            outcome=AuditOutcome.DENIED,
            operation=f"security_violation: {violation_type}",
            client_id=client_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            metadata={"violation_type": violation_type},
        )
        self.log_event(event)

    def log_rate_limit_exceeded(
        self,
        endpoint: str,
        client_id: str,
        retry_after: int,
        session_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log a rate limit exceeded event.

        Args:
            endpoint: Name of the rate-limited endpoint
            client_id: Client identifier
            retry_after: Seconds until retry is allowed
            session_id: Session identifier
            ip_address: Client IP address
        """
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            outcome=AuditOutcome.DENIED,
            operation=f"rate_limit_exceeded: {endpoint}",
            client_id=client_id,
            session_id=session_id,
            ip_address=ip_address,
            details={"endpoint": endpoint, "retry_after": retry_after},
        )
        self.log_event(event)

    def log_validation_failure(
        self,
        validation_type: str,
        input_value: str,
        reason: str,
        client_id: str = "unknown",
        session_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log a validation failure event.

        Args:
            validation_type: Type of validation that failed
            input_value: Input that failed validation
            reason: Reason for failure
            client_id: Client identifier
            session_id: Session identifier
            ip_address: Client IP address
        """
        event = AuditEvent(
            event_type=AuditEventType.VALIDATION_FAILURE,
            outcome=AuditOutcome.FAILURE,
            operation=f"validation_failure: {validation_type}",
            client_id=client_id,
            session_id=session_id,
            ip_address=ip_address,
            details={
                "validation_type": validation_type,
                "input_length": len(input_value),
                "reason": reason,
            },
        )
        self.log_event(event)

    def log_state_access(
        self,
        state_number: int,
        access_type: str,
        client_id: str = "system",
        session_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Log a state access event.

        Args:
            state_number: State number being accessed
            access_type: Type of access (e.g., "get_state_info", "search")
            client_id: Client identifier
            session_id: Session identifier
            success: Whether access succeeded
            error_message: Error message if failed
        """
        event = AuditEvent(
            event_type=AuditEventType.STATE_ACCESS,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            state_number=state_number,
            operation=f"state_access: {access_type}",
            client_id=client_id,
            session_id=session_id,
            error_message=error_message,
        )
        self.log_event(event)

    def _get_level_for_outcome(self, outcome: AuditOutcome) -> int:
        """Get logging level based on outcome.

        Args:
            outcome: Audit outcome

        Returns:
            Logging level
        """
        if outcome == AuditOutcome.DENIED:
            return logging.WARNING
        elif outcome == AuditOutcome.FAILURE:
            return logging.ERROR
        return logging.INFO

    def _flush_buffer(self) -> None:
        """Flush the events buffer (for internal use)."""
        self._events_buffer.clear()

    def get_events(
        self,
        event_type: AuditEventType | None = None,
        client_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get audit events from the buffer.

        Args:
            event_type: Filter by event type
            client_id: Filter by client ID
            limit: Maximum number of events to return

        Returns:
            List of audit events
        """
        with self._buffer_lock:
            events = list(self._events_buffer)

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if client_id:
            events = [e for e in events if e.client_id == client_id]

        return events[-limit:]

    def enable(self) -> None:
        """Enable audit logging."""
        self._enabled = True

    def disable(self) -> None:
        """Disable audit logging."""
        self._enabled = False

    def clear_buffer(self) -> None:
        """Clear the events buffer."""
        with self._buffer_lock:
            self._events_buffer.clear()


_audit_logger: AuditLogger | None = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.

    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        with _audit_logger_lock:
            if _audit_logger is None:
                from src.mcp_server.utils.logging import get_logger

                _audit_logger = AuditLogger(logger=get_logger("audit"))
    return _audit_logger


def set_audit_logger(audit_logger: AuditLogger) -> None:
    """Set the global audit logger instance (for testing).

    Args:
        audit_logger: AuditLogger instance to set
    """
    global _audit_logger
    _audit_logger = audit_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger (for testing)."""
    global _audit_logger
    _audit_logger = None


class AuditContext:
    """Context manager for automatic audit event logging."""

    def __init__(
        self,
        operation: str,
        event_type: AuditEventType,
        client_id: str = "system",
        session_id: str | None = None,
    ) -> None:
        self.operation = operation
        self.event_type = event_type
        self.client_id = client_id
        self.session_id = session_id
        self.start_time: float = 0
        self.success: bool = False
        self.error_message: str | None = None
        self.details: dict[str, Any] = {}

    def __enter__(self) -> "AuditContext":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)
        else:
            self.success = True

        audit_logger = get_audit_logger()

        if self.event_type == AuditEventType.STATE_TRANSITION:
            audit_logger.log_state_transition(
                from_state=self.details.get("from_state", 0),
                to_state=self.details.get("to_state", 0),
                success=self.success,
                client_id=self.client_id,
                session_id=self.session_id,
                duration_ms=duration_ms,
                error_message=self.error_message,
            )
        elif self.event_type == AuditEventType.ARBITRARY_TRANSITION:
            audit_logger.log_arbitrary_transition(
                from_state=self.details.get("from_state", 0),
                to_state=self.details.get("to_state", 0),
                success=self.success,
                client_id=self.client_id,
                session_id=self.session_id,
                duration_ms=duration_ms,
                error_message=self.error_message,
            )
        elif self.event_type == AuditEventType.GENESIS:
            audit_logger.log_genesis(
                success=self.success,
                client_id=self.client_id,
                session_id=self.session_id,
                duration_ms=duration_ms,
                error_message=self.error_message,
            )

    def set_details(self, key: str, value: Any) -> "AuditContext":
        """Set a detail to be included in the audit event.

        Args:
            key: Detail key
            value: Detail value

        Returns:
            Self for chaining
        """
        self.details[key] = value
        return self
