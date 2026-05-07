from unittest.mock import MagicMock, Mock, patch

from src.mcp_server.config import Settings
from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
from src.mcp_server.services.neo4j_bootstrap import prepare_neo4j_connection
from src.mcp_server.services.neo4j_service_manager import ManagedNeo4jConnection


class TestPrepareNeo4jConnection:
    def test_prepare_neo4j_connection_uses_auto_service_for_auto_mode(self, tmp_path):
        settings = Settings(
            db_mode="neo4j",
            neo4j_bootstrap_mode="auto",
            neo4j_auth_enabled=False,
        )
        managed_connection = ManagedNeo4jConnection(
            uri="bolt://127.0.0.1:17687",
            user="",
            password="",
            auth_enabled=False,
            container_name="codebase-state-manager-neo4j-test",
            bolt_port=17687,
            http_port=17474,
            data_dir=tmp_path / ".data" / "neo4j" / "data",
            logs_dir=tmp_path / ".data" / "neo4j" / "logs",
            runtime_file=tmp_path / ".data" / "neo4j" / "runtime.json",
            image="neo4j:5.24",
        )

        with patch("src.mcp_server.services.neo4j_bootstrap.ProjectNeo4jServiceManager") as manager_cls:
            manager_cls.return_value.ensure_service.return_value = managed_connection

            resolved = prepare_neo4j_connection(settings, project_root=tmp_path)

        assert resolved is settings
        assert resolved.neo4j_uri == "bolt://127.0.0.1:17687"
        assert resolved.neo4j_auth_enabled is False
        manager_cls.assert_called_once()

    def test_prepare_neo4j_connection_skips_auto_service_for_external_mode(self, tmp_path):
        settings = Settings(
            db_mode="neo4j",
            neo4j_bootstrap_mode="external",
            neo4j_uri="bolt://neo4j.example:7687",
            neo4j_user="neo4j",
            neo4j_password="secret",
            neo4j_auth_enabled=True,
        )

        with patch("src.mcp_server.services.neo4j_bootstrap.ProjectNeo4jServiceManager") as manager_cls:
            resolved = prepare_neo4j_connection(settings, project_root=tmp_path)

        assert resolved.neo4j_uri == "bolt://neo4j.example:7687"
        assert resolved.neo4j_password == "secret"
        manager_cls.assert_not_called()


class TestCreateNeo4jRepositories:
    def test_create_neo4j_repositories_disables_auth_when_requested(self):
        settings = Settings(db_mode="neo4j", neo4j_auth_enabled=False)

        with patch("src.mcp_server.repositories.neo4j_repository.GraphDatabase.driver") as driver_factory:
            driver = MagicMock()
            session = Mock()
            session.run.return_value = None
            driver.session.return_value.__enter__.return_value = session
            driver_factory.return_value = driver

            create_neo4j_repositories(
                uri="bolt://127.0.0.1:17687",
                user="neo4j",
                password="ignored",
                settings=settings,
            )

        assert driver_factory.call_args.kwargs["auth"] is None

    def test_create_neo4j_repositories_uses_credentials_when_auth_is_enabled(self):
        settings = Settings(db_mode="neo4j", neo4j_auth_enabled=True)

        with patch("src.mcp_server.repositories.neo4j_repository.GraphDatabase.driver") as driver_factory:
            driver = MagicMock()
            session = Mock()
            session.run.return_value = None
            driver.session.return_value.__enter__.return_value = session
            driver_factory.return_value = driver

            create_neo4j_repositories(
                uri="bolt://127.0.0.1:17687",
                user="neo4j",
                password="secret",
                settings=settings,
            )

        assert driver_factory.call_args.kwargs["auth"] == ("neo4j", "secret")
