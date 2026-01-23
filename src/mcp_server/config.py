import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


def _load_env_with_override() -> dict:
    """Load environment variables from .env file, but respect existing env vars.

    Returns:
        Dictionary of environment variables from .env file
    """
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path), override=True)
    return {}


class Settings:
    def __init__(  # nosec: B107
        self,
        neo4j_enabled: bool = True,
        db_mode: Literal["neo4j", "sqlite"] = "neo4j",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        neo4j_connection_timeout: int = 90,
        sqlite_path: str = "./data/state_manager.db",
        docker_volume_name: str = "./data/codebase_state_volume",
        docker_container_name: str = "codebase-state-manager",
        volume_path: str = "./data/codebase_state_volume",
        log_level: str = "INFO",
        rate_limit_enabled: bool = True,
        audit_enabled: bool = True,
        max_prompt_length: int = 10000,
        max_state_number: int = 1000000,
    ) -> None:
        self.neo4j_enabled = neo4j_enabled
        self.db_mode = db_mode
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.neo4j_connection_timeout = neo4j_connection_timeout
        self.sqlite_path = sqlite_path
        self.docker_volume_name = docker_volume_name
        self.docker_container_name = docker_container_name
        self.volume_path = volume_path
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

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_connection_timeout = int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "90"))
        sqlite_path = os.getenv("SQLITE_PATH", "./data/state_manager.db")
        docker_volume_name = os.getenv("DOCKER_VOLUME_NAME", "codebase_state_volume")
        docker_container_name = os.getenv("DOCKER_CONTAINER_NAME", "codebase-state-manager")
        volume_path = os.getenv("VOLUME_PATH", "./data/codebase_state_volume")
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
