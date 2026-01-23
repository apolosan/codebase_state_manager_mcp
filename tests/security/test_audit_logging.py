"""Tests for audit logging module."""

import logging

import pytest

from src.mcp_server.utils.audit import (
    AuditContext,
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditOutcome,
    get_audit_logger,
    reset_audit_logger,
    set_audit_logger,
)


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def audit_logger(self):
        """Create a fresh audit logger for each test."""
        reset_audit_logger()
        logger = AuditLogger()
        set_audit_logger(logger)
        yield logger
        reset_audit_logger()

    def test_log_event(self, audit_logger):
        """Test basic event logging."""
        event = AuditEvent(
            event_type=AuditEventType.STATE_TRANSITION,
            outcome=AuditOutcome.SUCCESS,
            operation="test_operation",
        )

        audit_logger.log_event(event)

    def test_log_state_transition(self, audit_logger):
        """Test state transition logging."""
        audit_logger.log_state_transition(
            from_state=0,
            to_state=1,
            success=True,
            prompt="Test prompt",
            client_id="test_client",
        )

        events = audit_logger.get_events(event_type=AuditEventType.STATE_TRANSITION)
        assert len(events) >= 1

        last_event = events[-1]
        assert last_event.previous_state == 0
        assert last_event.target_state == 1
        assert last_event.outcome == AuditOutcome.SUCCESS
        assert last_event.client_id == "test_client"

    def test_log_arbitrary_transition(self, audit_logger):
        """Test arbitrary transition logging."""
        audit_logger.log_arbitrary_transition(
            from_state=5,
            to_state=3,
            success=True,
            client_id="test_client",
        )

        events = audit_logger.get_events(event_type=AuditEventType.ARBITRARY_TRANSITION)
        assert len(events) >= 1

    def test_log_genesis(self, audit_logger):
        """Test genesis logging."""
        audit_logger.log_genesis(
            success=True,
            project_path="/test/path",
            client_id="test_client",
        )

        events = audit_logger.get_events(event_type=AuditEventType.GENESIS)
        assert len(events) >= 1

    def test_log_security_violation(self, audit_logger):
        """Test security violation logging."""
        audit_logger.log_security_violation(
            violation_type="CWE-78",
            details={"input": "; rm -rf /"},
            client_id="attacker",
            ip_address="192.168.1.1",
        )

        events = audit_logger.get_events(event_type=AuditEventType.SECURITY_VIOLATION)
        assert len(events) >= 1

        last_event = events[-1]
        assert last_event.metadata["violation_type"] == "CWE-78"
        assert last_event.outcome == AuditOutcome.DENIED

    def test_log_rate_limit_exceeded(self, audit_logger):
        """Test rate limit exceeded logging."""
        audit_logger.log_rate_limit_exceeded(
            endpoint="genesis",
            client_id="abuser",
            retry_after=60,
            ip_address="10.0.0.1",
        )

        events = audit_logger.get_events(event_type=AuditEventType.RATE_LIMIT_EXCEEDED)
        assert len(events) >= 1

    def test_log_validation_failure(self, audit_logger):
        """Test validation failure logging."""
        audit_logger.log_validation_failure(
            validation_type="prompt_sanitization",
            input_value="; rm -rf /",
            reason="Injection characters detected",
            client_id="test_client",
        )

        events = audit_logger.get_events(event_type=AuditEventType.VALIDATION_FAILURE)
        assert len(events) >= 1

    def test_log_state_access(self, audit_logger):
        """Test state access logging."""
        audit_logger.EVENT_TYPES_TO_LOG.add(AuditEventType.STATE_ACCESS)

        audit_logger.log_state_access(
            state_number=5,
            access_type="get_state_info",
            client_id="test_client",
            success=True,
        )

        events = audit_logger.get_events(event_type=AuditEventType.STATE_ACCESS)
        assert len(events) >= 1

    def test_get_events_with_filters(self, audit_logger):
        """Test getting events with filters."""
        audit_logger.log_state_transition(0, 1, True, client_id="client1")
        audit_logger.log_state_transition(1, 2, True, client_id="client2")
        audit_logger.log_state_transition(2, 3, True, client_id="client1")

        events = audit_logger.get_events(client_id="client1")
        assert len(events) >= 2

        for event in events:
            assert event.client_id == "client1"

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = AuditEvent(
            event_type=AuditEventType.STATE_TRANSITION,
            outcome=AuditOutcome.SUCCESS,
            operation="test",
            client_id="client",
            previous_state=0,
            target_state=1,
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "STATE_TRANSITION"
        assert event_dict["outcome"] == "SUCCESS"
        assert event_dict["client_id"] == "client"
        assert event_dict["previous_state"] == 0
        assert event_dict["target_state"] == 1

    def test_enable_disable(self, audit_logger):
        """Test enabling and disabling audit logger."""
        audit_logger.log_state_transition(0, 1, True)

        audit_logger.disable()

        audit_logger.log_state_transition(0, 1, True)

        events = audit_logger.get_events()
        assert len(events) == 1

        audit_logger.enable()

        audit_logger.log_state_transition(0, 1, True)

        events = audit_logger.get_events()
        assert len(events) >= 2

    def test_clear_buffer(self, audit_logger):
        """Test clearing the events buffer."""
        audit_logger.log_state_transition(0, 1, True)
        audit_logger.log_state_transition(1, 2, True)

        assert len(audit_logger.get_events()) >= 2

        audit_logger.clear_buffer()

        assert len(audit_logger.get_events()) == 0


class TestAuditContext:
    """Tests for AuditContext context manager."""

    @pytest.fixture
    def audit_logger(self):
        """Create a fresh audit logger for each test."""
        reset_audit_logger()
        logger = AuditLogger()
        set_audit_logger(logger)
        yield logger
        reset_audit_logger()

    def test_successful_operation(self, audit_logger):
        """Test context manager with successful operation."""
        with AuditContext(
            operation="test_operation",
            event_type=AuditEventType.STATE_TRANSITION,
            client_id="test_client",
        ) as ctx:
            ctx.set_details("from_state", 0)
            ctx.set_details("to_state", 1)

        events = audit_logger.get_events(event_type=AuditEventType.STATE_TRANSITION)
        assert len(events) >= 1

        last_event = events[-1]
        assert last_event.outcome == AuditOutcome.SUCCESS

    def test_failed_operation(self, audit_logger):
        """Test context manager with failed operation."""
        with pytest.raises(ValueError):
            with AuditContext(
                operation="test_operation",
                event_type=AuditEventType.STATE_TRANSITION,
                client_id="test_client",
            ) as ctx:
                raise ValueError("Test error")

        events = audit_logger.get_events(event_type=AuditEventType.STATE_TRANSITION)
        assert len(events) >= 1

        last_event = events[-1]
        assert last_event.outcome == AuditOutcome.FAILURE
        assert "Test error" in last_event.error_message


class TestGetAuditLogger:
    """Tests for get_audit_logger function."""

    def test_singleton_pattern(self):
        """Test that get_audit_logger returns singleton."""
        reset_audit_logger()

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2

        reset_audit_logger()

    def test_set_audit_logger(self):
        """Test setting a custom audit logger."""
        reset_audit_logger()

        custom_logger = AuditLogger()
        set_audit_logger(custom_logger)

        retrieved = get_audit_logger()

        assert retrieved is custom_logger

        reset_audit_logger()


class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_all_event_types_defined(self):
        """Test that all expected event types are defined."""
        expected_types = [
            "STATE_TRANSITION",
            "ARBITRARY_TRANSITION",
            "GENESIS",
            "STATE_ACCESS",
            "SEARCH",
            "CONFIG_CHANGE",
            "SECURITY_VIOLATION",
            "RATE_LIMIT_EXCEEDED",
            "VALIDATION_FAILURE",
            "INITIALIZATION",
            "ERROR",
        ]

        for event_type in expected_types:
            assert hasattr(AuditEventType, event_type)


class TestAuditOutcome:
    """Tests for AuditOutcome enum."""

    def test_all_outcomes_defined(self):
        """Test that all expected outcomes are defined."""
        assert hasattr(AuditOutcome, "SUCCESS")
        assert hasattr(AuditOutcome, "FAILURE")
        assert hasattr(AuditOutcome, "DENIED")
