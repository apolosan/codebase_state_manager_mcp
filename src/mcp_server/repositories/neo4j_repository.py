import json
from datetime import datetime
from typing import List, Optional

from neo4j import Driver, GraphDatabase

from ..config import Settings
from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..utils.hash import generate_state_hash


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
                         s.file_hash_deltas = $file_hash_deltas
                     RETURN s
                    """,
                    state_number=state.state_number,
                    user_prompt=state.user_prompt,
                    branch_name=state.branch_name,
                    git_diff_info=state.git_diff_info,
                    hash=state.hash,
                    created_at=state.created_at.isoformat() if state.created_at else None,
                    file_hash_deltas=(
                        json.dumps(state.file_hash_deltas) if state.file_hash_deltas else None
                    ),
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
                )
            return None

    def get_current(self) -> Optional[State]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:State)
                WITH s.state_number AS sn
                RETURN MAX(sn) AS max_state
                """)
            record = result.single()
            if record and record["max_state"]:
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
                            file_hash_deltas: $file_hash_deltas
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


class Neo4jTransitionRepository(TransitionRepository):
    def __init__(self, driver: Driver, settings: Settings) -> None:
        self.driver = driver
        self.settings = settings

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
                        timestamp: $timestamp
                    }]->(to)
                    RETURN t
                    """,
                    transition_id=transition.transition_id,
                    current_state=transition.current_state,
                    next_state=transition.next_state,
                    user_prompt=transition.user_prompt,
                    timestamp=transition.timestamp.isoformat() if transition.timestamp else None,
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
                timestamp: $timestamp
            }]->(to)
            RETURN t
            """,
            transition_id=next_id,
            current_state=transition.current_state,
            next_state=transition.next_state,
            user_prompt=transition.user_prompt,
            timestamp=transition.timestamp.isoformat() if transition.timestamp else None,
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
                t = record["t"]
                return Transition(
                    transition_id=t.get("transition_id", 0),
                    current_state=record["current_state"],
                    next_state=record["next_state"],
                    user_prompt=t.get("user_prompt"),
                    timestamp=(
                        datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else None
                    ),
                )
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
                t = record["t"]
                if t:
                    transitions.append(
                        Transition(
                            transition_id=t.get("transition_id", 0),
                            current_state=record["current_state"],
                            next_state=record["next_state"],
                            user_prompt=t.get("user_prompt"),
                            timestamp=(
                                datetime.fromisoformat(t["timestamp"])
                                if t.get("timestamp")
                                else None
                            ),
                        )
                    )
            return transitions

    def get_last(self, limit: int) -> List[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH ()-[t:TRANSITION]->()
                WITH t
                ORDER BY t.timestamp DESC
                LIMIT $limit
                RETURN t
                """,
                limit=limit,
            )
            transitions = []
            for record in result:
                t = record["t"]
                transitions.append(
                    Transition(
                        transition_id=t.get("transition_id", 0),
                        current_state=0,
                        next_state=0,
                        user_prompt=t.get("user_prompt"),
                        timestamp=(
                            datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else None
                        ),
                    )
                )
            return transitions

    def count(self) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH ()-[t:TRANSITION]->() RETURN COUNT(t) AS count")
            record = result.single()
            return int(record["count"]) if record else 0


def create_neo4j_repositories(
    uri: str, user: str, password: str, settings: Settings
) -> tuple[Neo4jStateRepository, Neo4jTransitionRepository]:
    connection_timeout_ms = settings.neo4j_connection_timeout * 1000
    driver = GraphDatabase.driver(
        uri,
        auth=(user, password),
        connection_timeout=connection_timeout_ms,
        max_connection_lifetime=3600 * 1000,
    )
    driver.verify_connectivity()
    return Neo4jStateRepository(driver, settings), Neo4jTransitionRepository(driver, settings)
