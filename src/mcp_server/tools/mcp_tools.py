from ..services.state_service import StateService


def genesis(
    state_service: StateService, project_path: str, volume_path: str
) -> dict:
    success, state, message = state_service.genesis(project_path, volume_path)
    return {
        "success": success,
        "state": state.to_dict() if state else None,
        "message": message,
    }


def new_state_transition(
    state_service: StateService, user_prompt: str, current_diff: str | None = None
) -> dict:
    success, state, message = state_service.new_state_transition(
        user_prompt, current_diff
    )
    return {
        "success": success,
        "state": state.to_dict() if state else None,
        "message": message,
    }


def arbitrary_state_transition(
    state_service: StateService, next_state: int, user_prompt: str | None = None
) -> dict:
    success, state, message = state_service.arbitrary_state_transition(
        next_state, user_prompt
    )
    return {
        "success": success,
        "state": state.to_dict() if state else None,
        "message": message,
    }


def get_current_state_number(state_service: StateService) -> dict:
    number, message = state_service.get_current_state_number()
    return {"success": number is not None, "state_number": number, "message": message}


def get_current_state_info(state_service: StateService) -> dict:
    state, message = state_service.get_current_state()
    return {
        "success": state is not None,
        "state": state.to_dict() if state else None,
        "message": message,
    }


def get_state_info(state_service: StateService, state: int) -> dict:
    state_obj, message = state_service.get_state_info(state)
    return {
        "success": state_obj is not None,
        "state": state_obj.to_dict() if state_obj else None,
        "message": message,
    }


def total_states(state_service: StateService) -> dict:
    count, message = state_service.total_states()
    return {"success": True, "total_states": count, "message": message}


def search_states(state_service: StateService, text: str) -> dict:
    results, message = state_service.search_states(text)
    return {"success": True, "states": results, "message": message}


def get_state_transitions(state_service: StateService, state: int) -> dict:
    transitions, message = state_service.get_state_transitions(state)
    return {"success": True, "transitions": transitions, "message": message}


def get_transition_info(state_service: StateService, transition_id: str) -> dict:
    transition, message = state_service.get_transition_info(transition_id)
    return {"success": transition is not None, "transition": transition, "message": message}


def track_transitions(state_service: StateService) -> dict:
    transitions, message = state_service.track_transitions()
    return {"success": True, "transitions": transitions, "message": message}
