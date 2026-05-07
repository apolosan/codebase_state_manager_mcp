"""Automatic project-scoped Neo4j lifecycle management."""

from __future__ import annotations

import hashlib
import json
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import docker
from docker.client import DockerClient
from docker.errors import DockerException
from docker.models.containers import Container
from neo4j import GraphDatabase

from ..config import Settings


class Neo4jServiceError(RuntimeError):
    """Raised when the managed Neo4j service cannot be prepared."""


@dataclass(frozen=True)
class ManagedNeo4jConnection:
    """Resolved connection information for the managed Neo4j service."""

    uri: str
    user: str
    password: str | None
    auth_enabled: bool
    container_name: str
    bolt_port: int
    http_port: int
    data_dir: Path
    logs_dir: Path
    runtime_file: Path
    image: str


@dataclass
class ManagedNeo4jRuntimeState:
    """Persisted runtime state for a project-scoped Neo4j instance."""

    container_name: str
    bolt_port: int
    http_port: int
    data_dir: Path
    logs_dir: Path
    runtime_file: Path
    image: str
    auth_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialize runtime state to a JSON-safe payload."""
        return {
            "container_name": self.container_name,
            "bolt_port": self.bolt_port,
            "http_port": self.http_port,
            "data_dir": str(self.data_dir),
            "logs_dir": str(self.logs_dir),
            "runtime_file": str(self.runtime_file),
            "image": self.image,
            "auth_enabled": self.auth_enabled,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ManagedNeo4jRuntimeState":
        """Deserialize runtime state from JSON payload."""
        return cls(
            container_name=str(payload["container_name"]),
            bolt_port=int(str(payload["bolt_port"])),
            http_port=int(str(payload["http_port"])),
            data_dir=Path(str(payload["data_dir"])),
            logs_dir=Path(str(payload["logs_dir"])),
            runtime_file=Path(str(payload["runtime_file"])),
            image=str(payload["image"]),
            auth_enabled=bool(payload.get("auth_enabled", False)),
        )


class ProjectNeo4jServiceManager:
    """Manage a persistent Neo4j container per project root."""

    def __init__(
        self,
        project_root: Path,
        settings: Settings,
        client_factory: Optional[Callable[[], DockerClient]] = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_root = project_root.resolve()
        self.settings = settings
        self.client_factory = client_factory or docker.from_env
        self.sleep_func = sleep_func

    def ensure_service(self) -> ManagedNeo4jConnection:
        """Ensure the project-scoped Neo4j service is running and ready."""
        runtime_state = self._load_runtime_state() or self._build_runtime_state()
        self._ensure_runtime_directories(runtime_state)

        client = self._get_client()
        container = self._find_container(client, runtime_state.container_name)

        if container is None:
            container = self._create_container(client, runtime_state)
        else:
            self._start_container_if_needed(container)

        connection = self._connection_from_container(container, runtime_state)
        self._persist_runtime_state(runtime_state)
        self._wait_until_ready(connection)
        return connection

    def _runtime_home(self) -> Path:
        auto_home = Path(self.settings.neo4j_auto_home)
        if auto_home.is_absolute():
            return auto_home
        return (self.project_root / auto_home).resolve()

    def _project_hash(self) -> str:
        return hashlib.sha256(str(self.project_root).encode("utf-8")).hexdigest()[:12]

    def _build_runtime_state(self) -> ManagedNeo4jRuntimeState:
        runtime_home = self._runtime_home()
        bolt_port = self._find_available_port()
        http_port = self._find_available_port()
        while http_port == bolt_port:
            http_port = self._find_available_port()
        return ManagedNeo4jRuntimeState(
            container_name=f"codebase-state-manager-neo4j-{self._project_hash()}",
            bolt_port=bolt_port,
            http_port=http_port,
            data_dir=runtime_home / "data",
            logs_dir=runtime_home / "logs",
            runtime_file=runtime_home / "runtime.json",
            image=self.settings.neo4j_auto_image,
            auth_enabled=False,
        )

    def _ensure_runtime_directories(self, runtime_state: ManagedNeo4jRuntimeState) -> None:
        runtime_state.data_dir.mkdir(parents=True, exist_ok=True)
        runtime_state.logs_dir.mkdir(parents=True, exist_ok=True)
        runtime_state.runtime_file.parent.mkdir(parents=True, exist_ok=True)

    def _persist_runtime_state(self, runtime_state: ManagedNeo4jRuntimeState) -> None:
        self._ensure_runtime_directories(runtime_state)
        runtime_state.runtime_file.write_text(json.dumps(runtime_state.to_dict(), indent=2))

    def _load_runtime_state(self) -> Optional[ManagedNeo4jRuntimeState]:
        runtime_file = self._runtime_home() / "runtime.json"
        if not runtime_file.exists():
            return None

        payload = json.loads(runtime_file.read_text())
        if not isinstance(payload, dict):
            raise Neo4jServiceError("Invalid Neo4j runtime file format")
        return ManagedNeo4jRuntimeState.from_dict(payload)

    def _get_client(self) -> DockerClient:
        try:
            client = self.client_factory()
            client.ping()
            return client
        except DockerException as exc:
            raise Neo4jServiceError(f"Docker unavailable for managed Neo4j: {exc}") from exc

    def _find_container(self, client: DockerClient, container_name: str) -> Optional[Container]:
        containers = client.containers.list(all=True, filters={"name": container_name})
        if not containers:
            return None
        return containers[0]

    def _create_container(
        self,
        client: DockerClient,
        runtime_state: ManagedNeo4jRuntimeState,
    ) -> Container:
        return client.containers.run(
            runtime_state.image,
            name=runtime_state.container_name,
            detach=True,
            environment={"NEO4J_AUTH": "none"},
            ports={
                "7687/tcp": runtime_state.bolt_port,
                "7474/tcp": runtime_state.http_port,
            },
            volumes={
                str(runtime_state.data_dir): {"bind": "/data", "mode": "rw"},
                str(runtime_state.logs_dir): {"bind": "/logs", "mode": "rw"},
            },
            labels={
                "codebase-state-manager": "true",
                "codebase-state-manager.project_root": str(self.project_root),
            },
            restart_policy={"Name": "unless-stopped"},
        )

    def _start_container_if_needed(self, container: Container) -> None:
        if container.status != "running":
            container.start()
        container.reload()

    def _published_port(self, container: Container, key: str) -> Optional[int]:
        container.reload()
        network_settings = container.attrs.get("NetworkSettings", {})
        if not isinstance(network_settings, dict):
            return None
        ports = network_settings.get("Ports", {})
        if not isinstance(ports, dict):
            return None
        bindings = ports.get(key)
        if not bindings or not isinstance(bindings, list):
            return None
        binding = bindings[0]
        if not isinstance(binding, dict):
            return None
        host_port = binding.get("HostPort")
        if host_port is None:
            return None
        return int(str(host_port))

    def _connection_from_container(
        self,
        container: Container,
        runtime_state: ManagedNeo4jRuntimeState,
    ) -> ManagedNeo4jConnection:
        bolt_port = self._published_port(container, "7687/tcp") or runtime_state.bolt_port
        http_port = self._published_port(container, "7474/tcp") or runtime_state.http_port
        runtime_state.bolt_port = bolt_port
        runtime_state.http_port = http_port
        return ManagedNeo4jConnection(
            uri=f"bolt://127.0.0.1:{bolt_port}",
            user="",
            password=None,
            auth_enabled=False,
            container_name=runtime_state.container_name,
            bolt_port=bolt_port,
            http_port=http_port,
            data_dir=runtime_state.data_dir,
            logs_dir=runtime_state.logs_dir,
            runtime_file=runtime_state.runtime_file,
            image=runtime_state.image,
        )

    def _wait_until_ready(self, connection: ManagedNeo4jConnection) -> None:
        deadline = time.time() + self.settings.neo4j_connection_timeout
        while time.time() < deadline:
            try:
                driver = GraphDatabase.driver(connection.uri, auth=None)
                try:
                    driver.verify_connectivity()
                    return
                finally:
                    driver.close()
            except Exception:
                self.sleep_func(1)
        raise Neo4jServiceError(
            f"Managed Neo4j at {connection.uri} did not become ready within "
            f"{self.settings.neo4j_connection_timeout}s"
        )

    def _find_available_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return int(sock.getsockname()[1])
