import json
import math
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


def validate_reward(value: float | None) -> float | None:
    """Validate a transition reward value.

    Args:
        value: Reward to validate.

    Returns:
        The validated reward or None.

    Raises:
        ValidationError: If the reward is invalid.
    """
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("Reward deve ser numérico ou null")

    reward = float(value)
    if math.isnan(reward) or math.isinf(reward):
        raise ValidationError("Reward deve ser um número finito")

    if reward < -10 or reward > 10:
        raise ValidationError("Reward deve estar no intervalo [-10, 10]")

    return reward


def _validate_compact_diff_item(item: object) -> None:
    if not isinstance(item, dict):
        raise ValidationError("Cada item de d deve ser um objeto JSON")

    required_keys = {"p", "a", "s"}
    if not required_keys.issubset(item.keys()):
        raise ValidationError("Cada item de d deve conter p, a e s")

    path_id = item["p"]
    action = item["a"]
    size = item["s"]

    if isinstance(path_id, bool) or not isinstance(path_id, int):
        raise ValidationError("Campo d[].p deve ser inteiro")
    if not isinstance(action, str) or action not in {"A", "M", "D"}:
        raise ValidationError("Campo d[].a deve ser um de A, M ou D")
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValidationError("Campo d[].s deve ser inteiro")


def _validate_compact_hash_item(item: object) -> None:
    if not isinstance(item, dict):
        raise ValidationError("Cada item de h deve ser um objeto JSON")

    required_keys = {"i", "h"}
    if not required_keys.issubset(item.keys()):
        raise ValidationError("Cada item de h deve conter i e h")

    hash_id = item["i"]
    hash_value = item["h"]

    if isinstance(hash_id, bool) or not isinstance(hash_id, int):
        raise ValidationError("Campo h[].i deve ser inteiro")
    if not isinstance(hash_value, str) or not hash_value:
        raise ValidationError("Campo h[].h deve ser string não vazia")


def validate_llm_context(value: str | None) -> str | None:
    """Validate an SCC-E compact state payload.

    Args:
        value: JSON string payload or None.

    Returns:
        The original payload when valid, or None.

    Raises:
        ValidationError: If the payload is invalid.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValidationError("llm_context deve ser uma string JSON ou null")

    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"llm_context deve ser JSON válido: {exc}")

    if not isinstance(payload, dict):
        raise ValidationError("llm_context deve ser um objeto JSON")

    expected_keys = {"v", "d", "h"}
    if set(payload.keys()) != expected_keys:
        raise ValidationError("llm_context deve conter exatamente as chaves v, d e h")

    version = payload.get("v")
    if version != "scc-e:v1":
        raise ValidationError("llm_context deve usar a versão scc-e:v1")

    diffs = payload.get("d")
    hashes = payload.get("h")

    if not isinstance(diffs, list):
        raise ValidationError("llm_context.d deve ser uma lista")
    if not isinstance(hashes, list):
        raise ValidationError("llm_context.h deve ser uma lista")

    for diff_item in diffs:
        _validate_compact_diff_item(diff_item)

    for hash_item in hashes:
        _validate_compact_hash_item(hash_item)

    return value
