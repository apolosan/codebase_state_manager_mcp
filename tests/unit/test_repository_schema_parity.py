from src.mcp_server.repositories.neo4j_repository import (
    STATE_PROPERTY_NAMES,
    TRANSITION_PROPERTY_NAMES,
)
from src.mcp_server.repositories.sqlite_repository import StateModel, TransitionModel


class TestRepositorySchemaParity:
    def test_state_fields_match_between_sqlite_and_neo4j(self):
        sqlite_columns = {column.name for column in StateModel.__table__.columns}

        assert STATE_PROPERTY_NAMES == sqlite_columns

    def test_transition_fields_match_between_sqlite_and_neo4j(self):
        sqlite_columns = {column.name for column in TransitionModel.__table__.columns}
        normalized_sqlite_columns = {
            "transition_id" if column_name == "id" else column_name
            for column_name in sqlite_columns
        }

        assert TRANSITION_PROPERTY_NAMES == normalized_sqlite_columns
