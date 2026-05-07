import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


DEFAULT_VOLUME_ROOT = Path("/opt/codebase-state-manager/volumes")


def _load_env_with_override() -> dict:
    """Load environment variables from .env file, but respect existing env vars.

    Returns:
        Dictionary of environment variables from .env file
    """
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path), override=False)
    return {}


def _get_default_volume_path(project_path: Path | None = None) -> str:
    """Return the default managed volume root for the current project.

    When VOLUME_PATH is not explicitly configured, the server keeps managed snapshots
    outside the project tree under /opt using the current project directory name.
    """
    resolved_project_path = (project_path or Path.cwd()).resolve()
    project_name = resolved_project_path.name or "project"
    return str(DEFAULT_VOLUME_ROOT / project_name)


class Settings:
    def __init__(  # nosec: B107
        self,
        neo4j_enabled: bool = True,
        db_mode: Literal["neo4j", "sqlite"] = "neo4j",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        neo4j_bootstrap_mode: Literal["auto", "external"] = "auto",
        neo4j_auth_enabled: bool = False,
        neo4j_auto_image: str = "neo4j:5.24",
        neo4j_auto_home: str = "./.data/neo4j",
        neo4j_connection_timeout: int = 90,
        sqlite_path: str = "./data/state_manager.db",
        docker_volume_name: str | None = None,
        docker_container_name: str = "codebase-state-manager",
        volume_path: str | None = None,
        log_level: str = "INFO",
        rate_limit_enabled: bool = True,
        audit_enabled: bool = True,
        max_prompt_length: int = 10000,
        max_state_number: int = 1000000,
    ) -> None:
        self.neo4j_enabled = neo4j_enabled
        self.db_mode = db_mode
        resolved_bootstrap_mode = neo4j_bootstrap_mode
        if resolved_bootstrap_mode == "auto" and neo4j_password:
            resolved_bootstrap_mode = "external"

        resolved_auth_enabled = neo4j_auth_enabled
        if resolved_bootstrap_mode == "external" and not neo4j_auth_enabled:
            resolved_auth_enabled = bool(neo4j_password)

        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.neo4j_bootstrap_mode = resolved_bootstrap_mode
        self.neo4j_auth_enabled = resolved_auth_enabled
        resolved_volume_path = volume_path
        if resolved_volume_path is None:
            resolved_volume_path = docker_volume_name or _get_default_volume_path()

        resolved_docker_volume_name = docker_volume_name or resolved_volume_path

        self.neo4j_auto_image = neo4j_auto_image
        self.neo4j_auto_home = neo4j_auto_home
        self.neo4j_connection_timeout = neo4j_connection_timeout
        self.sqlite_path = sqlite_path
        self.docker_volume_name = resolved_docker_volume_name
        self.docker_container_name = docker_container_name
        self.volume_path = resolved_volume_path
        self.log_level = log_level
        self.rate_limit_enabled = rate_limit_enabled
        self.audit_enabled = audit_enabled
        self.max_prompt_length = max_prompt_length
        self.max_state_number = max_state_number

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_with_override()

        neo4j_enabled_raw = os.getenv("NEO4J_ENABLED", "true")
        neo4j_enabled = neo4j_enabled_raw.lower() in ("true", "1", "yes")

        db_mode_raw = os.getenv("DB_MODE", "")
        if db_mode_raw in ("neo4j", "sqlite"):
            db_mode: Literal["neo4j", "sqlite"] = db_mode_raw  # type: ignore[assignment]
        else:
            db_mode = "neo4j" if neo4j_enabled else "sqlite"

        neo4j_uri_env = os.getenv("NEO4J_URI")
        neo4j_user_env = os.getenv("NEO4J_USER")
        neo4j_password_env = os.getenv("NEO4J_PASSWORD")
        neo4j_bootstrap_mode_raw = os.getenv("NEO4J_BOOTSTRAP_MODE", "").lower()
        if neo4j_bootstrap_mode_raw in ("auto", "external"):
            neo4j_bootstrap_mode: Literal["auto", "external"] = neo4j_bootstrap_mode_raw  # type: ignore[assignment]
        else:
            explicit_neo4j_config = any(
                value is not None
                for value in (neo4j_uri_env, neo4j_user_env, neo4j_password_env)
            )
            neo4j_bootstrap_mode = "external" if explicit_neo4j_config else "auto"

        neo4j_uri = neo4j_uri_env or "bolt://localhost:7687"
        neo4j_user = neo4j_user_env or "neo4j"
        neo4j_password = neo4j_password_env or ""

        neo4j_auth_enabled_raw = os.getenv("NEO4J_AUTH_ENABLED", "")
        if neo4j_auth_enabled_raw:
            neo4j_auth_enabled = neo4j_auth_enabled_raw.lower() in ("true", "1", "yes")
        else:
            neo4j_auth_enabled = neo4j_bootstrap_mode == "external"

        neo4j_auto_image = os.getenv("NEO4J_AUTO_IMAGE", "neo4j:5.24")
        neo4j_auto_home = os.getenv("NEO4J_AUTO_HOME", "./.data/neo4j")
        neo4j_connection_timeout = int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "90"))
        sqlite_path = os.getenv("SQLITE_PATH", "./data/state_manager.db")
        docker_container_name = os.getenv("DOCKER_CONTAINER_NAME", "codebase-state-manager")
        volume_path = os.getenv("VOLUME_PATH") or _get_default_volume_path()
        docker_volume_name = volume_path  # Use same path for consistency
        log_level = os.getenv("LOG_LEVEL", "INFO")
        rate_limit_enabled_raw = os.getenv("RATE_LIMIT_ENABLED", "true")
        rate_limit_enabled = rate_limit_enabled_raw.lower() in ("true", "1", "yes")
        audit_enabled_raw = os.getenv("AUDIT_ENABLED", "true")
        audit_enabled = audit_enabled_raw.lower() in ("true", "1", "yes")
        max_prompt_length = int(os.getenv("MAX_PROMPT_LENGTH", "10000"))
        max_state_number = int(os.getenv("MAX_STATE_NUMBER", "1000000"))

        return cls(
            neo4j_enabled=neo4j_enabled,
            db_mode=db_mode,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_bootstrap_mode=neo4j_bootstrap_mode,
            neo4j_auth_enabled=neo4j_auth_enabled,
            neo4j_auto_image=neo4j_auto_image,
            neo4j_auto_home=neo4j_auto_home,
            neo4j_connection_timeout=neo4j_connection_timeout,
            sqlite_path=sqlite_path,
            docker_volume_name=docker_volume_name,
            docker_container_name=docker_container_name,
            volume_path=volume_path,
            log_level=log_level,
            rate_limit_enabled=rate_limit_enabled,
            audit_enabled=audit_enabled,
            max_prompt_length=max_prompt_length,
            max_state_number=max_state_number,
        )

    def to_dict(self) -> dict:
        return {
            "neo4j_enabled": self.neo4j_enabled,
            "db_mode": self.db_mode,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": "***" if self.neo4j_password else "",
            "neo4j_bootstrap_mode": self.neo4j_bootstrap_mode,
            "neo4j_auth_enabled": self.neo4j_auth_enabled,
            "neo4j_auto_image": self.neo4j_auto_image,
            "neo4j_auto_home": self.neo4j_auto_home,
            "neo4j_connection_timeout": self.neo4j_connection_timeout,
            "sqlite_path": self.sqlite_path,
            "docker_volume_name": self.docker_volume_name,
            "docker_container_name": self.docker_container_name,
            "volume_path": self.volume_path,
            "log_level": self.log_level,
            "rate_limit_enabled": self.rate_limit_enabled,
            "audit_enabled": self.audit_enabled,
            "max_prompt_length": self.max_prompt_length,
            "max_state_number": self.max_state_number,
        }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
