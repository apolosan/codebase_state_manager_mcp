"""Tests for __main__.py entry point."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMainEntryPoint:
    """Test the main entry point functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.log_level = "INFO"
        settings.db_mode = "sqlite"
        settings.rate_limit_enabled = True
        settings.audit_enabled = True
        settings.neo4j_uri = "bolt://localhost:7687"
        settings.neo4j_user = "neo4j"
        settings.neo4j_password = "password"
        settings.sqlite_path = ":memory:"
        return settings

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        state_repo = MagicMock()
        transition_repo = MagicMock()
        transition_repo.count.return_value = 0
        return state_repo, transition_repo

    def test_main_with_sqlite_mode(self, mock_settings, mock_repositories, capsys):
        """Test main function with SQLite database mode."""
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging") as mock_setup_logging,
            patch("src.mcp_server.utils.logging.get_logger") as mock_get_logger,
            patch("src.mcp_server.utils.security.get_rate_limiter") as mock_get_rate_limiter,
            patch("src.mcp_server.utils.audit.get_audit_logger") as mock_get_audit_logger,
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager") as mock_git_manager_class,
            patch("src.mcp_server.services.state_service.StateService") as mock_state_service_class,
            patch("src.mcp_server.tools.mcp_tools"),
        ):

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_rate_limiter = MagicMock()
            mock_get_rate_limiter.return_value = mock_rate_limiter
            mock_audit_logger = MagicMock()
            mock_get_audit_logger.return_value = mock_audit_logger

            # Import and call main
            from src.mcp_server.__main__ import main

            # Mock app.run to prevent stdin/stdout blocking
            with patch("src.mcp_server.mcp_server.app.run") as mock_app_run:
                main()

            mock_setup_logging.assert_called_once_with(log_level="INFO")
            mock_get_logger.assert_called()
            mock_rate_limiter.enable.assert_called_once()
            mock_audit_logger.enable.assert_called_once()
            assert mock_logger.info.called
            assert any(
                "Starting" in str(call) or "MCP Server" in str(call)
                for call in mock_logger.info.call_args_list
            )
            mock_app_run.assert_called_once()

    def test_main_with_neo4j_mode(self, mock_settings, mock_repositories, capsys):
        """Test main function with Neo4j database mode."""
        mock_settings.db_mode = "neo4j"
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging") as mock_setup_logging,
            patch("src.mcp_server.utils.logging.get_logger") as mock_get_logger,
            patch("src.mcp_server.utils.security.get_rate_limiter") as mock_get_rate_limiter,
            patch("src.mcp_server.utils.audit.get_audit_logger") as mock_get_audit_logger,
            patch(
                "src.mcp_server.repositories.neo4j_repository.create_neo4j_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager") as mock_git_manager_class,
            patch("src.mcp_server.services.state_service.StateService") as mock_state_service_class,
            patch("src.mcp_server.tools.mcp_tools"),
        ):

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_rate_limiter = MagicMock()
            mock_get_rate_limiter.return_value = mock_rate_limiter
            mock_audit_logger = MagicMock()
            mock_get_audit_logger.return_value = mock_audit_logger

            from src.mcp_server.__main__ import main

            # Mock app.run to prevent stdin/stdout blocking
            with patch("src.mcp_server.mcp_server.app.run") as mock_app_run:
                main()

            assert mock_logger.info.called
            assert any(
                "Neo4j" in str(call) or "Connected" in str(call)
                for call in mock_logger.info.call_args_list
            )
            mock_app_run.assert_called_once()

    def test_main_disables_rate_limiting_when_disabled(self, mock_settings, mock_repositories):
        """Test that rate limiting is disabled when configured."""
        mock_settings.rate_limit_enabled = False
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging"),
            patch("src.mcp_server.utils.logging.get_logger"),
            patch("src.mcp_server.utils.security.get_rate_limiter") as mock_get_rate_limiter,
            patch("src.mcp_server.utils.audit.get_audit_logger"),
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager"),
            patch("src.mcp_server.services.state_service.StateService"),
            patch("src.mcp_server.tools.mcp_tools"),
            patch("src.mcp_server.mcp_server.app.run") as mock_app_run,
        ):

            mock_rate_limiter = MagicMock()
            mock_get_rate_limiter.return_value = mock_rate_limiter

            from src.mcp_server.__main__ import main

            main()

            mock_app_run.assert_called_once()
            mock_rate_limiter.disable.assert_called_once()
            mock_rate_limiter.enable.assert_not_called()

    def test_main_disables_audit_when_disabled(self, mock_settings, mock_repositories):
        """Test that audit logging is disabled when configured."""
        mock_settings.audit_enabled = False
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging"),
            patch("src.mcp_server.utils.logging.get_logger"),
            patch("src.mcp_server.utils.security.get_rate_limiter") as mock_get_rate_limiter,
            patch("src.mcp_server.utils.audit.get_audit_logger") as mock_get_audit_logger,
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager"),
            patch("src.mcp_server.services.state_service.StateService"),
            patch("src.mcp_server.tools.mcp_tools"),
            patch("src.mcp_server.mcp_server.app.run") as mock_app_run,
        ):

            mock_rate_limiter = MagicMock()
            mock_get_rate_limiter.return_value = mock_rate_limiter
            mock_audit_logger = MagicMock()
            mock_get_audit_logger.return_value = mock_audit_logger

            from src.mcp_server.__main__ import main

            main()

            mock_app_run.assert_called_once()
            mock_audit_logger.disable.assert_called_once()
            mock_audit_logger.enable.assert_not_called()

    def test_main_initializes_state_service(self, mock_settings, mock_repositories):
        """Test that StateService is properly initialized."""
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging"),
            patch("src.mcp_server.utils.logging.get_logger"),
            patch("src.mcp_server.utils.security.get_rate_limiter"),
            patch("src.mcp_server.utils.audit.get_audit_logger"),
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager") as mock_git_manager_class,
            patch("src.mcp_server.services.state_service.StateService") as mock_state_service_class,
            patch("src.mcp_server.tools.mcp_tools"),
            patch("src.mcp_server.mcp_server.app.run") as mock_app_run,
        ):

            mock_git_manager = MagicMock()
            mock_git_manager_class.return_value = mock_git_manager

            from src.mcp_server.__main__ import main

            main()

            mock_app_run.assert_called_once()
            mock_state_service_class.assert_called_once_with(
                state_repo=state_repo,
                transition_repo=transition_repo,
                git_manager=mock_git_manager,
                settings=mock_settings,
            )

    def test_main_logs_available_tools(self, mock_settings, mock_repositories):
        """Test that available MCP tools are logged."""
        state_repo, transition_repo = mock_repositories

        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging"),
            patch("src.mcp_server.utils.logging.get_logger") as mock_get_logger,
            patch("src.mcp_server.utils.security.get_rate_limiter"),
            patch("src.mcp_server.utils.audit.get_audit_logger"),
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager"),
            patch("src.mcp_server.services.state_service.StateService"),
            patch("src.mcp_server.tools.mcp_tools"),
            patch("src.mcp_server.mcp_server.app.run") as mock_app_run,
        ):

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            from src.mcp_server.__main__ import main

            main()

            mock_app_run.assert_called_once()
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            has_tool_logging = any("Available MCP Tools" in str(call) for call in log_calls)
            assert has_tool_logging, "Should log available MCP tools"


class TestMainLoggingSetup:
    """Test logging setup in main function."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with different log levels."""
        settings = MagicMock()
        settings.log_level = "DEBUG"
        settings.db_mode = "sqlite"
        settings.rate_limit_enabled = False
        settings.audit_enabled = False
        settings.sqlite_path = ":memory:"
        return settings

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        state_repo = MagicMock()
        transition_repo = MagicMock()
        transition_repo.count.return_value = 0
        return state_repo, transition_repo

    def test_setup_logging_with_debug_level(self, mock_settings, mock_repositories):
        """Test that logging is set up with the configured level."""
        with (
            patch("src.mcp_server.config.get_settings", return_value=mock_settings),
            patch("src.mcp_server.utils.logging.setup_logging") as mock_setup_logging,
            patch("src.mcp_server.utils.logging.get_logger"),
            patch("src.mcp_server.utils.security.get_rate_limiter"),
            patch("src.mcp_server.utils.audit.get_audit_logger"),
            patch(
                "src.mcp_server.repositories.sqlite_repository.create_sqlite_repositories",
                return_value=mock_repositories,
            ),
            patch("src.mcp_server.services.git_manager.GitManager"),
            patch("src.mcp_server.services.state_service.StateService"),
            patch("src.mcp_server.tools.mcp_tools"),
            patch("src.mcp_server.mcp_server.app.run") as mock_app_run,
        ):

            from src.mcp_server.__main__ import main

            main()

            mock_app_run.assert_called_once()
            mock_setup_logging.assert_called_once_with(log_level="DEBUG")


class TestMainSysPath:
    """Test the sys.path manipulation in __main__."""

    def test_sys_path_contains_project_root(self):
        """Test that project root is in sys.path after module load."""
        import importlib.util
        import sys
        from pathlib import Path

        module_path = Path(
            "/home/einar/Documentos/codebase_state_manager_mcp/src/mcp_server/__main__.py"
        )
        spec = importlib.util.spec_from_file_location("__main__", str(module_path))
        assert spec is not None, "Module spec should not be None"
        module = importlib.util.module_from_spec(spec)

        project_root = str(module_path.parent.parent)
        original_path = sys.path.copy()
        try:
            assert project_root in sys.path or str(module_path.parent) in sys.path
        finally:
            sys.path[:] = original_path
