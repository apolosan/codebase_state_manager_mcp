"""MCP Tools for Codebase State Manager.

Provides all the MCP server tools for managing codebase states.
Includes rate limiting and audit logging for security.
"""

import time
from typing import Any

from ..services.state_service import StateService
from ..utils.audit import AuditEventType, AuditOutcome, get_audit_logger
from ..utils.logging import get_logger
from ..utils.security import RateLimitExceeded, get_rate_limiter

logger = get_logger(__name__)


def _handle_rate_limit(client_id: str, endpoint: str) -> dict:
    """Handle rate limiting for an endpoint.

    Args:
        client_id: Client identifier
        endpoint: Endpoint name

    Returns:
        Error dict if rate limited, empty dict otherwise
    """
    rate_limiter = get_rate_limiter()
    try:
        rate_limiter.check_rate_limit(client_id, endpoint)
        return {}
    except RateLimitExceeded as e:
        audit_logger = get_audit_logger()
        audit_logger.log_rate_limit_exceeded(
            endpoint=endpoint,
            client_id=client_id,
            retry_after=e.retry_after,
        )
        return {
            "success": False,
            "error": "rate_limit_exceeded",
            "message": str(e),
            "retry_after": e.retry_after,
        }


def genesis(
    state_service: StateService,
    project_path: str,
    volume_path: str,
    client_id: str = "default",
) -> dict:
    """Initialize the state machine for a project.

    Args:
        state_service: StateService instance
        project_path: Path to the project
        volume_path: Path for the Docker volume
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state, and message
    """
    rate_result = _handle_rate_limit(client_id, "genesis")
    if rate_result:
        return rate_result

    start_time = time.time()
    audit_logger = get_audit_logger()

    try:
        success, state, message = state_service.genesis(project_path, volume_path)

        duration_ms = int((time.time() - start_time) * 1000)

        audit_logger.log_genesis(
            success=success,
            project_path=project_path,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=None if success else message,
        )

        if success:
            logger.info(
                "Genesis completed",
                extra={"operation": "genesis", "client_id": client_id, "duration_ms": duration_ms},
            )

        return {
            "success": success,
            "state": state.to_dict() if state else None,
            "message": message,
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        audit_logger.log_genesis(
            success=False,
            project_path=project_path,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        logger.error(f"Genesis failed: {e}", extra={"operation": "genesis", "client_id": client_id})
        raise


def new_state_transition(
    state_service: StateService,
    user_prompt: str,
    client_id: str = "default",
) -> dict:
    """Perform a new state transition.

    Args:
        state_service: StateService instance
        user_prompt: User prompt for the transition
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state, and message
    """
    rate_result = _handle_rate_limit(client_id, "new_state_transition")
    if rate_result:
        return rate_result

    start_time = time.time()
    audit_logger = get_audit_logger()

    try:
        current_state = state_service.state_repo.get_current()
        from_state = current_state.state_number if current_state else -1

        success, state, message = state_service.new_state_transition(user_prompt)

        to_state_num = state.state_number if state else -1

        duration_ms = int((time.time() - start_time) * 1000)

        audit_logger.log_state_transition(
            from_state=from_state,
            to_state=to_state_num,
            success=success,
            prompt=user_prompt,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=None if success else message,
        )

        if success:
            logger.info(
                f"State transition completed: {from_state} -> {to_state_num}",
                extra={
                    "operation": "new_state_transition",
                    "client_id": client_id,
                    "from_state": from_state,
                    "to_state": to_state_num,
                    "duration_ms": duration_ms,
                },
            )

        return {
            "success": success,
            "state": state.to_dict() if state else None,
            "message": message,
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        audit_logger.log_state_transition(
            from_state=-1,
            to_state=-1,
            success=False,
            prompt=user_prompt,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        logger.error(
            f"State transition failed: {e}",
            extra={"operation": "new_state_transition", "client_id": client_id},
        )
        raise


def arbitrary_state_transition(
    state_service: StateService,
    next_state: int,
    user_prompt: str | None = None,
    client_id: str = "default",
) -> dict:
    """Perform an arbitrary state transition.

    Args:
        state_service: StateService instance
        next_state: Target state number
        user_prompt: Optional user prompt
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state, and message
    """
    rate_result = _handle_rate_limit(client_id, "arbitrary_state_transition")
    if rate_result:
        return rate_result

    start_time = time.time()
    audit_logger = get_audit_logger()

    try:
        current_state = state_service.state_repo.get_current()
        from_state = current_state.state_number if current_state else -1

        success, state, message = state_service.arbitrary_state_transition(next_state, user_prompt)

        duration_ms = int((time.time() - start_time) * 1000)

        audit_logger.log_arbitrary_transition(
            from_state=from_state,
            to_state=next_state,
            success=success,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=None if success else message,
        )

        if success:
            logger.info(
                f"Arbitrary transition completed: {from_state} -> {next_state}",
                extra={
                    "operation": "arbitrary_state_transition",
                    "client_id": client_id,
                    "from_state": from_state,
                    "to_state": next_state,
                    "duration_ms": duration_ms,
                },
            )

        return {
            "success": success,
            "state": state.to_dict() if state else None,
            "message": message,
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        audit_logger.log_arbitrary_transition(
            from_state=-1,
            to_state=next_state,
            success=False,
            client_id=client_id,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        logger.error(
            f"Arbitrary transition failed: {e}",
            extra={"operation": "arbitrary_state_transition", "client_id": client_id},
        )
        raise


def get_current_state_number(
    state_service: StateService,
    client_id: str = "default",
) -> dict:
    """Get the current state number.

    Args:
        state_service: StateService instance
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state number, and message
    """
    rate_result = _handle_rate_limit(client_id, "get_current_state_info")
    if rate_result:
        return rate_result

    number, message = state_service.get_current_state_number()
    return {"success": number is not None, "state_number": number, "message": message}


def get_current_state_info(
    state_service: StateService,
    client_id: str = "default",
) -> dict:
    """Get the current state information.

    Args:
        state_service: StateService instance
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state, and message
    """
    rate_result = _handle_rate_limit(client_id, "get_current_state_info")
    if rate_result:
        return rate_result

    state, message = state_service.get_current_state()
    return {
        "success": state is not None,
        "state": state.to_dict() if state else None,
        "message": message,
    }


def get_state_info(
    state_service: StateService,
    state: int,
    client_id: str = "default",
) -> dict:
    """Get information for a specific state.

    Args:
        state_service: StateService instance
        state: State number
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, state, and message
    """
    rate_result = _handle_rate_limit(client_id, "get_state_info")
    if rate_result:
        return rate_result

    state_obj, message = state_service.get_state_info(state)
    return {
        "success": state_obj is not None,
        "state": state_obj.to_dict() if state_obj else None,
        "message": message,
    }


def total_states(
    state_service: StateService,
    client_id: str = "default",
) -> dict:
    """Get the total number of states.

    Args:
        state_service: StateService instance
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, total states, and message
    """
    rate_result = _handle_rate_limit(client_id, "total_states")
    if rate_result:
        return rate_result

    count, message = state_service.total_states()
    return {"success": True, "total_states": count, "message": message}


def search_states(
    state_service: StateService,
    text: str,
    client_id: str = "default",
) -> dict:
    """Search for states containing the given text.

    Args:
        state_service: StateService instance
        text: Search text
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, matching states, and message
    """
    rate_result = _handle_rate_limit(client_id, "search_states")
    if rate_result:
        return rate_result

    results, message = state_service.search_states(text)
    return {"success": True, "states": results, "message": message}


def get_state_transitions(
    state_service: StateService,
    state: int,
    client_id: str = "default",
) -> dict:
    """Get transitions for a specific state.

    Args:
        state_service: StateService instance
        state: State number
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, transitions, and message
    """
    rate_result = _handle_rate_limit(client_id, "get_state_transitions")
    if rate_result:
        return rate_result

    transitions, message = state_service.get_state_transitions(state)
    return {"success": True, "transitions": transitions, "message": message}


def get_transition_info(
    state_service: StateService,
    transition_id: str,
    client_id: str = "default",
) -> dict:
    """Get information for a specific transition.

    Args:
        state_service: StateService instance
        transition_id: Transition ID
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, transition, and message
    """
    rate_result = _handle_rate_limit(client_id, "get_transition_info")
    if rate_result:
        return rate_result

    transition, message = state_service.get_transition_info(transition_id)
    return {"success": transition is not None, "transition": transition, "message": message}


def track_transitions(
    state_service: StateService,
    client_id: str = "default",
) -> dict:
    """Get the last 5 transitions.

    Args:
        state_service: StateService instance
        client_id: Client identifier for rate limiting

    Returns:
        Dict with success status, transitions, and message
    """
    rate_result = _handle_rate_limit(client_id, "track_transitions")
    if rate_result:
        return rate_result

    transitions, message = state_service.track_transitions()
    return {"success": True, "transitions": transitions, "message": message}
