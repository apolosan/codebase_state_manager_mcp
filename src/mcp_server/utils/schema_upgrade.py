"""SQLite schema upgrades for backward-compatible column additions."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

STATE_COLUMN_DEFINITIONS = {
    "llm_context": "TEXT NULL",
    "compression_version": "VARCHAR(32) NULL",
    "compacted_at": "DATETIME NULL",
}

TRANSITION_COLUMN_DEFINITIONS = {
    "reward": "REAL NULL",
}


def _column_names(engine: Engine, table_name: str) -> set[str]:
    with engine.connect() as connection:
        result = connection.execute(text(f"PRAGMA table_info({table_name})"))
        return {str(row[1]) for row in result}


def _ensure_table_columns(engine: Engine, table_name: str, definitions: dict[str, str]) -> None:
    existing_columns = _column_names(engine, table_name)
    missing_columns = {
        column_name: definition
        for column_name, definition in definitions.items()
        if column_name not in existing_columns
    }

    if not missing_columns:
        return

    with engine.begin() as connection:
        for column_name, definition in missing_columns.items():
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
            )


def ensure_schema_columns(engine: Engine) -> None:
    """Ensure optional SCC-E and reward columns exist in SQLite tables."""
    _ensure_table_columns(engine, "states", STATE_COLUMN_DEFINITIONS)
    _ensure_table_columns(engine, "transitions", TRANSITION_COLUMN_DEFINITIONS)
