import json
from datetime import datetime
from typing import List, Optional

from neo4j import Driver, GraphDatabase

from ..config import Settings
from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..utils.hash import generate_state_hash

STATE_PROPERTY_NAMES = {
    "state_number",
    "user_prompt",
    "branch_name",
    "git_diff_info",
    "hash",
    "created_at",
    "file_hashes",
    "file_hash_deltas",
    "llm_context",
    "compression_version",
    "compacted_at",
}

TRANSITION_PROPERTY_NAMES = {
    "transition_id",
    "current_state",
    "next_state",
    "user_prompt",
    "timestamp",
    "reward",
}


class Neo4jStateRepository(StateRepository):
    def __init__(self, driver: Driver, settings: Settings) -> None:
        self.driver = driver
        self.settings = settings
        self._init_constraints()

    def _init_constraints(self) -> None:
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.state_number IS UNIQUE"
            )
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.hash IS UNIQUE")

    def create(self, state: State) -> bool:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MERGE (s:State {state_number: $state_number})
                    SET s.user_prompt = $user_prompt,
                        s.branch_name = $branch_name,
                        s.git_diff_info = $git_diff_info,
                        s.hash = $hash,
                        s.created_at = $created_at,
                        s.file_hashes = $file_hashes,
                        s.file_hash_deltas = $file_hash_deltas,
                        s.llm_context = $llm_context,
                        s.compression_version = $compression_version,
                        s.compacted_at = $compacted_at
                    RETURN s
                    """,
                    state_number=state.state_number,
                    user_prompt=state.user_prompt,
                    branch_name=state.branch_name,
                    git_diff_info=state.git_diff_info,
                    hash=state.hash,
                    created_at=state.created_at.isoformat() if state.created_at else None,
                    file_hashes=json.dumps(state.file_hashes) if state.file_hashes else None,
                    file_hash_deltas=(
                        json.dumps(state.file_hash_deltas) if state.file_hash_deltas else None
                    ),
                    llm_context=state.llm_context,
                    compression_version=state.compression_version,
                    compacted_at=state.compacted_at.isoformat() if state.compacted_at else None,
                )
                return result.single() is not None
            except Exception:
                return False

    def get_by_number(self, state_number: int) -> Optional[State]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:State {state_number: $state_number})
                RETURN s
                """,
                state_number=state_number,
            )
            record = result.single()
            if record:
                s = record["s"]
                file_hashes = s.get("file_hashes")
                if file_hashes is not None:
                    if isinstance(file_hashes, str):
                        try:
                            file_hashes = json.loads(file_hashes)
                        except json.JSONDecodeError:
                            file_hashes = {}
                    else:
                        file_hashes = file_hashes or {}
                # file_hashes can be None for transition states
                file_hash_deltas = s.get("file_hash_deltas", {}) or {}
                if isinstance(file_hash_deltas, str):
                    try:
                        file_hash_deltas = json.loads(file_hash_deltas)
                    except json.JSONDecodeError:
                        file_hash_deltas = {}
                return State(
                    state_number=s.get("state_number", 0),
                    user_prompt=s.get("user_prompt", ""),
                    branch_name=s.get("branch_name", ""),
                    git_diff_info=s.get("git_diff_info", ""),
                    hash=s.get("hash", ""),
                    created_at=(
                        datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None
                    ),
                    file_hashes=file_hashes,
                    file_hash_deltas=file_hash_deltas,
                    llm_context=s.get("llm_context"),
                    compression_version=s.get("compression_version"),
                    compacted_at=(
                        datetime.fromisoformat(s["compacted_at"])
                        if s.get("compacted_at")
                        else None
                    ),
                )
            return None

    def get_current(self) -> Optional[State]:
        with self.driver.session() as session:
            metadata_result = session.run("""
                MATCH (m:Metadata {key: 'current_state'})
                RETURN m.state_number AS state_number
                """)
            metadata_record = metadata_result.single()
            if metadata_record and metadata_record["state_number"] is not None:
                return self.get_by_number(metadata_record["state_number"])

            result = session.run("""
                MATCH (s:State)
                WITH s.state_number AS sn
                RETURN MAX(sn) AS max_state
                """)
            record = result.single()
            if record and record["max_state"] is not None:
                return self.get_by_number(record["max_state"])
            return None

    def get_all(self) -> List[State]:
        with self.driver.session() as session:
            result = session.run("MATCH (s:State) RETURN s ORDER BY s.state_number")
            states = []
            for record in result:
                s = record["s"]
                file_hashes = s.get("file_hashes")
                if file_hashes is not None:
                    if isinstance(file_hashes, str):
                        try:
                            file_hashes = json.loads(file_hashes)
                        except json.JSONDecodeError:
                            file_hashes = {}
                    else:
                        file_hashes = file_hashes or {}
                # file_hashes can be None for transition states
                file_hash_deltas = s.get("file_hash_deltas", {}) or {}
                if isinstance(file_hash_deltas, str):
                    try:
                        file_hash_deltas = json.loads(file_hash_deltas)
                    except json.JSONDecodeError:
                        file_hash_deltas = {}
                states.append(
                    State(
                        state_number=s.get("state_number", 0),
                        user_prompt=s.get("user_prompt", ""),
                        branch_name=s.get("branch_name", ""),
                        git_diff_info=s.get("git_diff_info", ""),
                        hash=s.get("hash", ""),
                        created_at=(
                            datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None
                        ),
                        file_hashes=file_hashes,
                        file_hash_deltas=file_hash_deltas,
                        llm_context=s.get("llm_context"),
                        compression_version=s.get("compression_version"),
                        compacted_at=(
                            datetime.fromisoformat(s["compacted_at"])
                            if s.get("compacted_at")
                            else None
                        ),
                    )
                )
            return states

    def exists(self, state_number: int) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:State {state_number: $state_number})
                RETURN COUNT(s) AS count
                """,
                state_number=state_number,
            )
            record = result.single()
            return record is not None and record["count"] > 0

    def count(self) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH (s:State) RETURN COUNT(s) AS count")
            record = result.single()
            return int(record["count"]) if record else 0

    def search(self, text: str) -> List[int]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:State)
                WHERE s.user_prompt CONTAINS $text
                RETURN s.state_number AS state_number
                ORDER BY s.state_number
                """,
                text=text,
            )
            return [record["state_number"] for record in result]

    def delete(self, state_number: int) -> bool:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MATCH (s:State {state_number: $state_number})
                    DELETE s
                    RETURN COUNT(s) AS deleted
                    """,
                    state_number=state_number,
                )
                record = result.single()
                return record is not None and record["deleted"] > 0
            except Exception:
                return False

    def create_next(self, state: State) -> bool:
        """Create a new state with the next sequential state number."""
        with self.driver.session() as session:
            try:
                # Use write transaction for atomicity
                def create_tx(tx):
                    # Get current maximum state number
                    result = tx.run("MATCH (s:State) RETURN MAX(s.state_number) AS max_state")
                    record = result.single()
                    max_state = (
                        record["max_state"] if record and record["max_state"] is not None else -1
                    )
                    next_state_number = max_state + 1

                    # Generate hash with the correct state number
                    state_hash = generate_state_hash(
                        state.user_prompt,
                        state.branch_name,
                        state.git_diff_info,
                        next_state_number,
                    )

                    # Create the new state node
                    result = tx.run(
                        """
                        CREATE (new:State {
                            state_number: $state_number,
                            user_prompt: $user_prompt,
                            branch_name: $branch_name,
                            git_diff_info: $git_diff_info,
                            hash: $hash,
                            created_at: $created_at,
                            file_hash_deltas: $file_hash_deltas,
                            llm_context: $llm_context,
                            compression_version: $compression_version,
                            compacted_at: $compacted_at
                        })
                        RETURN new.state_number AS state_number
                        """,
                        state_number=next_state_number,
                        user_prompt=state.user_prompt,
                        branch_name=state.branch_name,
                        git_diff_info=state.git_diff_info,
                        hash=state_hash,
                        created_at=state.created_at.isoformat() if state.created_at else None,
                        file_hash_deltas=(
                            json.dumps(state.file_hash_deltas) if state.file_hash_deltas else None
                        ),
                        llm_context=state.llm_context,
                        compression_version=state.compression_version,
                        compacted_at=state.compacted_at.isoformat() if state.compacted_at else None,
                    )
                    record = result.single()
                    if record:
                        state.state_number = record["state_number"]
                        state.hash = state_hash
                        return True
                    return False

                return session.execute_write(create_tx)
            except Exception:
                return False

    def set_current(self, state_number: int) -> bool:
        """Set the current state explicitly for arbitrary transitions."""
        with self.driver.session() as session:
            try:
                state_exists = session.run(
                    "MATCH (s:State {state_number: $state_number}) RETURN COUNT(s) AS count",
                    state_number=state_number,
                ).single()
                if not state_exists or state_exists["count"] == 0:
                    return False

                session.run(
                    """
                    MERGE (m:Metadata {key: 'current_state'})
                    SET m.state_number = $state_number
                    """,
                    state_number=state_number,
                )
                return True
            except Exception:
                return False

    def get_metadata(self, key: str) -> Optional[str]:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MATCH (m:Metadata {key: $key})
                    RETURN m.value AS value, m.state_number AS state_number
                    """,
                    key=key,
                )
                record = result.single()
                if not record:
                    return None
                if record.get("value") is not None:
                    return str(record["value"])
                if record.get("state_number") is not None:
                    return str(record["state_number"])
                return None
            except Exception:
                return None

    def set_metadata(self, key: str, value: str) -> bool:
        with self.driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (m:Metadata {key: $key})
                    SET m.value = $value
                    REMOVE m.state_number
                    """,
                    key=key,
                    value=value,
                )
                return True
            except Exception:
                return False


class Neo4jTransitionRepository(TransitionRepository):
    def __init__(self, driver: Driver, settings: Settings) -> None:
        self.driver = driver
        self.settings = settings

    def _build_transition(self, record) -> Transition:
        transition_data = record["t"]
        return Transition(
            transition_id=transition_data.get("transition_id", 0),
            current_state=record.get("current_state", 0),
            next_state=record.get("next_state", 0),
            user_prompt=transition_data.get("user_prompt"),
            timestamp=(
                datetime.fromisoformat(transition_data["timestamp"])
                if transition_data.get("timestamp")
                else None
            ),
            reward=transition_data.get("reward"),
        )

    def create(self, transition: Transition) -> bool:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MERGE (from:State {state_number: $current_state})
                    MERGE (to:State {state_number: $next_state})
                    CREATE (from)-[t:TRANSITION {
                        transition_id: $transition_id,
                        user_prompt: $user_prompt,
                        timestamp: $timestamp,
                        reward: $reward
                    }]->(to)
                    RETURN t
                    """,
                    transition_id=transition.transition_id,
                    current_state=transition.current_state,
                    next_state=transition.next_state,
                    user_prompt=transition.user_prompt,
                    timestamp=transition.timestamp.isoformat() if transition.timestamp else None,
                    reward=transition.reward,
                )
                return result.single() is not None
            except Exception:
                return False

    def create_next(self, transition: Transition) -> bool:
        """Create a new transition with the next sequential transition ID."""
        with self.driver.session() as session:
            try:
                # Use write transaction for atomicity
                result = session.execute_write(self._create_next_transaction, transition)
                return result
            except Exception:
                return False

    def _create_next_transaction(self, tx, transition: Transition) -> bool:
        """Transaction function for create_next."""
        # Get current maximum transition ID
        max_result = tx.run("MATCH ()-[t:TRANSITION]->() RETURN MAX(t.transition_id) AS max_id")
        max_record = max_result.single()
        max_id = max_record["max_id"] if max_record and max_record["max_id"] is not None else 0
        next_id = max_id + 1

        # Create transition with new ID
        result = tx.run(
            """
            MERGE (from:State {state_number: $current_state})
            MERGE (to:State {state_number: $next_state})
            CREATE (from)-[t:TRANSITION {
                transition_id: $transition_id,
                user_prompt: $user_prompt,
                timestamp: $timestamp,
                reward: $reward
            }]->(to)
            RETURN t
            """,
            transition_id=next_id,
            current_state=transition.current_state,
            next_state=transition.next_state,
            user_prompt=transition.user_prompt,
            timestamp=transition.timestamp.isoformat() if transition.timestamp else None,
            reward=transition.reward,
        )
        if result.single():
            # Update the transition object with the new ID
            transition.transition_id = next_id
            return True
        return False

    def get_by_id(self, transition_id: int) -> Optional[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:State)-[t:TRANSITION {transition_id: $transition_id}]->(to:State)
                RETURN t, from.state_number AS current_state, to.state_number AS next_state
                """,
                transition_id=transition_id,
            )
            record = result.single()
            if record:
                return self._build_transition(record)
            return None

    def get_by_state(self, state_number: int) -> List[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:State {state_number: $state_number})
                OPTIONAL MATCH (s)-[t:TRANSITION]->(next:State)
                RETURN t, s.state_number AS current_state, next.state_number AS next_state
                """,
                state_number=state_number,
            )
            transitions = []
            for record in result:
                if record["t"]:
                    transitions.append(self._build_transition(record))
            return transitions

    def get_last(self, limit: int) -> List[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:State)-[t:TRANSITION]->(to:State)
                WITH t, from, to
                ORDER BY t.timestamp DESC
                LIMIT $limit
                RETURN t, from.state_number AS current_state, to.state_number AS next_state
                """,
                limit=limit,
            )
            transitions = []
            for record in result:
                transitions.append(self._build_transition(record))
            return transitions

    def count(self) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH ()-[t:TRANSITION]->() RETURN COUNT(t) AS count")
            record = result.single()
            return int(record["count"]) if record else 0

    def delete(self, transition_id: int) -> bool:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MATCH ()-[t:TRANSITION {transition_id: $transition_id}]->()
                    WITH t
                    DELETE t
                    RETURN 1 AS deleted
                    """,
                    transition_id=transition_id,
                )
                return result.single() is not None
            except Exception:
                return False

    def get_rewarded(self) -> List[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:State)-[t:TRANSITION]->(to:State)
                WHERE t.reward IS NOT NULL
                RETURN t, from.state_number AS current_state, to.state_number AS next_state
                ORDER BY t.transition_id
                """
            )
            return [self._build_transition(record) for record in result]

    def get_by_state_pair(self, current_state: int, next_state: int) -> List[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:State {state_number: $current_state})-[t:TRANSITION]->
                      (to:State {state_number: $next_state})
                RETURN t, from.state_number AS current_state, to.state_number AS next_state
                ORDER BY t.transition_id
                """,
                current_state=current_state,
                next_state=next_state,
            )
            return [self._build_transition(record) for record in result]

    def update_reward(self, transition_id: int, reward: float | None) -> bool:
        with self.driver.session() as session:
            try:
                result = session.run(
                    """
                    MATCH ()-[t:TRANSITION {transition_id: $transition_id}]->()
                    SET t.reward = $reward
                    RETURN t
                    """,
                    transition_id=transition_id,
                    reward=reward,
                )
                return result.single() is not None
            except Exception:
                return False


def create_neo4j_repositories(
    uri: str, user: str, password: str, settings: Settings
) -> tuple[Neo4jStateRepository, Neo4jTransitionRepository]:
    connection_timeout_ms = settings.neo4j_connection_timeout * 1000
    auth = (user, password) if settings.neo4j_auth_enabled else None
    driver = GraphDatabase.driver(
        uri,
        auth=auth,
        connection_timeout=connection_timeout_ms,
        max_connection_lifetime=3600 * 1000,
    )
    driver.verify_connectivity()
    return Neo4jStateRepository(driver, settings), Neo4jTransitionRepository(driver, settings)
