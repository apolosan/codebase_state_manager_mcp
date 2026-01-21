import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(
        self,
        db_mode: Literal["neo4j", "sqlite"] = "neo4j",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        sqlite_path: str = "./data/state_manager.db",
        docker_volume_name: str = "codebase_state_volume",
        docker_container_name: str = "codebase-state-manager",
        log_level: str = "INFO",
    ) -> None:
        self.db_mode = db_mode
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.sqlite_path = sqlite_path
        self.docker_volume_name = docker_volume_name
        self.docker_container_name = docker_container_name
        self.log_level = log_level

    @classmethod
    def from_env(cls) -> "Settings":
        db_mode_raw = os.getenv("DB_MODE", "neo4j")
        db_mode: Literal["neo4j", "sqlite"] = "neo4j" if db_mode_raw in ("neo4j", "sqlite") else "neo4j"
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        sqlite_path = os.getenv("SQLITE_PATH", "./data/state_manager.db")
        docker_volume_name = os.getenv("DOCKER_VOLUME_NAME", "codebase_state_volume")
        docker_container_name = os.getenv(
            "DOCKER_CONTAINER_NAME", "codebase-state-manager"
        )
        log_level = os.getenv("LOG_LEVEL", "INFO")
        return cls(
            db_mode=db_mode,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            sqlite_path=sqlite_path,
            docker_volume_name=docker_volume_name,
            docker_container_name=docker_container_name,
            log_level=log_level,
        )

    def to_dict(self) -> dict:
        return {
            "db_mode": self.db_mode,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": "***" if self.neo4j_password else "",
            "sqlite_path": self.sqlite_path,
            "docker_volume_name": self.docker_volume_name,
            "docker_container_name": self.docker_container_name,
            "log_level": self.log_level,
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
