import re
from pathlib import Path
from typing import Optional

CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
INJECTION_PATTERN = re.compile(r"[;&|`$\n]")
PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\./|\.\.\\|%2e%2e)")

MAX_PROMPT_LENGTH = 10000
MAX_PATH_LENGTH = 4096


class ValidationError(Exception):
    """Exceção para erros de validação."""

    pass


def sanitize_prompt(prompt: str, max_length: Optional[int] = None) -> str:
    """
    Sanitiza um prompt de usuário para prevenir injection attacks.

    Args:
        prompt: O prompt a ser sanitizado
        max_length: Comprimento máximo opcional

    Returns:
        Prompt sanitizado

    Raises:
        ValidationError: Se o prompt for inválido
    """
    if not isinstance(prompt, str):
        raise ValidationError("Prompt deve ser uma string")

    if not prompt:
        raise ValidationError("Prompt não pode estar vazio")

    cleaned = CONTROL_CHARS_PATTERN.sub("", prompt)

    if INJECTION_PATTERN.search(cleaned):
        raise ValidationError("Prompt contém caracteres potencialmente perigosos para injeção")

    max_len = max_length if max_length is not None else MAX_PROMPT_LENGTH
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]

    return cleaned.strip()


def validate_path(path: str, base_path: Path) -> Path:
    """
    Valida e resolve um caminho contra um diretório base.
    Previne path traversal attacks.

    Args:
        path: O caminho a ser validado
        base_path: O diretório base permitido

    Returns:
        O caminho resolved e validado

    Raises:
        ValidationError: Se o caminho for inválido ou fora do base_path
    """
    if not isinstance(path, str):
        raise ValidationError("Caminho deve ser uma string")

    if not path:
        raise ValidationError("Caminho não pode estar vazio")

    if len(path) > MAX_PATH_LENGTH:
        raise ValidationError(f"Caminho excede o limite de {MAX_PATH_LENGTH} caracteres")

    if PATH_TRAVERSAL_PATTERN.search(path.lower()):
        raise ValidationError("Caminho contém padrões de path traversal detectados")

    resolved_base = base_path.resolve()

    try:
        resolved_path = (base_path / path).resolve()
    except (OSError, ValueError) as e:
        raise ValidationError(f"Caminho inválido: {e}")

    if not resolved_path.is_relative_to(resolved_base):
        raise ValidationError("Caminho está fora do diretório permitido")

    return resolved_path


def validate_state_number(state: int, max_states: int) -> int:
    """
    Valida um número de estado.

    Args:
        state: O número do estado a ser validado
        max_states: Número máximo de estados permitidos

    Returns:
        O estado validado

    Raises:
        ValidationError: Se o estado for inválido
    """
    if not isinstance(state, int):
        raise ValidationError("Estado deve ser um inteiro")

    if state < 0:
        raise ValidationError("Estado não pode ser negativo")

    if state >= max_states:
        raise ValidationError(f"Estado {state} excede o máximo de {max_states - 1}")

    return state


def validate_state_range(from_state: int, to_state: int, max_states: int) -> tuple[int, int]:
    """
    Valida um range de estados para transições arbitrárias.

    Args:
        from_state: Estado de origem
        to_state: Estado de destino
        max_states: Número máximo de estados

    Returns:
        Tuple com os estados validados

    Raises:
        ValidationError: Se o range for inválido
    """
    if not isinstance(from_state, int) or not isinstance(to_state, int):
        raise ValidationError("Estados devem ser inteiros")

    if from_state < 0 or to_state < 0:
        raise ValidationError("Estados não podem ser negativos")

    if from_state >= max_states or to_state >= max_states:
        raise ValidationError(f"Estados excedem o limite máximo de {max_states - 1}")

    if from_state == to_state:
        raise ValidationError("Transição de estado para o mesmo estado não é permitida")

    return from_state, to_state


def sanitize_branch_name(branch_name: str) -> str:
    """
    Sanitiza um nome de branch git.

    Args:
        branch_name: O nome do branch

    Returns:
        Nome do branch sanitizado
    """
    if not isinstance(branch_name, str):
        raise ValidationError("Nome de branch deve ser uma string")

    sanitized = re.sub(r"[^\w/-]", "_", branch_name)

    sanitized = sanitized.strip("_")

    if not sanitized or len(sanitized) > 255:
        raise ValidationError("Nome de branch inválido após sanitização")

    return sanitized


def validate_diff_info(diff_info: str, max_size: int = 100000) -> str:
    """
    Valida informações de diff.

    Args:
        diff_info: O diff a ser validado
        max_size: Tamanho máximo permitido em caracteres

    Returns:
        Diff validado (truncado se necessário)
    """
    if not isinstance(diff_info, str):
        raise ValidationError("Diff deve ser uma string")

    if len(diff_info) > max_size:
        return diff_info[:max_size] + "... [truncated]"

    return diff_info


TRANSITION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_transition_id(transition_id: str) -> str:
    """Validate a transition ID format (UUID v4).

    Args:
        transition_id: The transition ID to validate

    Returns:
        The validated transition ID

    Raises:
        ValidationError: If the transition ID is invalid
    """
    if not isinstance(transition_id, str):
        raise ValidationError("Transition ID deve ser uma string")

    if not TRANSITION_ID_PATTERN.match(transition_id):
        raise ValidationError(
            "Transition ID deve ser um UUID válido (formato: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
        )

    return transition_id


def validate_rate_limit_params(client_id: str, endpoint: str) -> tuple[str, str]:
    """Validate rate limit parameters.

    Args:
        client_id: Client identifier
        endpoint: Endpoint name

    Returns:
        Tuple of validated (client_id, endpoint)

    Raises:
        ValidationError: If parameters are invalid
    """
    if not isinstance(client_id, str):
        raise ValidationError("Client ID deve ser uma string")

    if not isinstance(endpoint, str):
        raise ValidationError("Endpoint deve ser uma string")

    if len(client_id) > 256:
        raise ValidationError("Client ID muito longo (max 256 caracteres)")

    if len(endpoint) > 128:
        raise ValidationError("Endpoint muito longo (max 128 caracteres)")

    if not client_id.strip():
        raise ValidationError("Client ID não pode estar vazio")

    if not endpoint.strip():
        raise ValidationError("Endpoint não pode estar vazio")

    return client_id.strip(), endpoint.strip()


def validate_search_text(text: str, max_length: int = 1000) -> str:
    """Validate search text input.

    Args:
        text: Search text to validate
        max_length: Maximum allowed length

    Returns:
        Validated search text

    Raises:
        ValidationError: If text is invalid
    """
    if not isinstance(text, str):
        raise ValidationError("Search text deve ser uma string")

    text = text.strip()

    if not text:
        raise ValidationError("Search text não pode estar vazio")

    if len(text) > max_length:
        raise ValidationError(f"Search text muito longo (max {max_length} caracteres)")

    control_chars = CONTROL_CHARS_PATTERN.search(text)
    if control_chars:
        raise ValidationError("Search text contém caracteres de controle inválidos")

    return text


def sanitize_for_json(value: str, max_length: int = 10000) -> str:
    """Sanitize a string for safe JSON inclusion.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValidationError: If value is invalid
    """
    if not isinstance(value, str):
        raise ValidationError("Value deve ser uma string")

    if len(value) > max_length:
        value = value[:max_length]

    cleaned = CONTROL_CHARS_PATTERN.sub("", value)

    return cleaned


def validate_volume_path(volume_path: str) -> Path:
    """Validate volume path for Docker volumes.

    Args:
        volume_path: The volume path to validate

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(volume_path, str):
        raise ValidationError("Volume path deve ser uma string")

    if not volume_path.strip():
        raise ValidationError("Volume path não pode estar vazio")

    if len(volume_path) > MAX_PATH_LENGTH:
        raise ValidationError(f"Volume path muito longo (max {MAX_PATH_LENGTH} caracteres)")

    if PATH_TRAVERSAL_PATTERN.search(volume_path.lower()):
        raise ValidationError("Volume path contém padrões de path traversal")

    if volume_path.startswith("/"):
        abs_path = Path(volume_path)
    else:
        abs_path = Path.cwd() / volume_path

    try:
        resolved = abs_path.resolve()
    except (OSError, ValueError) as e:
        raise ValidationError(f"Volume path inválido: {e}")

    return resolved
