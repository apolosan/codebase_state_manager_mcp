from unittest.mock import MagicMock

from src.mcp_server.config import Settings
from src.mcp_server.repositories.neo4j_repository import Neo4jStateRepository


class TestNeo4jStateRepositoryUnit:
    def test_get_current_returns_genesis_when_max_state_is_zero_without_metadata(self):
        driver = MagicMock()
        metadata_session = driver.session.return_value.__enter__.return_value
        metadata_result = MagicMock()
        metadata_result.single.side_effect = [None, {"max_state": 0}]
        metadata_session.run.return_value = metadata_result

        settings = Settings(db_mode="neo4j")
        repository = Neo4jStateRepository(driver, settings)
        repository.get_by_number = MagicMock(return_value="genesis-state")

        current = repository.get_current()

        assert current == "genesis-state"
        repository.get_by_number.assert_called_once_with(0)
