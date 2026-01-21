from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from neo4j import GraphDatabase

from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..config import Settings


class Neo4jStateRepository(StateRepository):
    def __init__(self, driver: GraphDatabase.driver, settings: Settings) -> None:
        self.driver = driver
        self.settings = settings
        self._init_constraints()

    def _init_constraints(self) -> None:
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.state_number IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.hash IS UNIQUE"
            )

    def create(self, state: State) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MERGE (s:State {state_number: $state_number})
                SET s.user_prompt = $user_prompt,
                    s.branch_name = $branch_name,
                    s.git_diff_info = $git_diff_info,
                    s.hash = $hash,
                    s.created_at = $created_at
                RETURN s
                """,
                state_number=state.state_number,
                user_prompt=state.user_prompt,
                branch_name=state.branch_name,
                git_diff_info=state.git_diff_info,
                hash=state.hash,
                created_at=state.created_at.isoformat() if state.created_at else None,
            )
            return result.single() is not None

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
                return State(
                    state_number=s.get("state_number", 0),
                    user_prompt=s.get("user_prompt", ""),
                    branch_name=s.get("branch_name", ""),
                    git_diff_info=s.get("git_diff_info", ""),
                    hash=s.get("hash", ""),
                    created_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None,
                )
            return None

    def get_current(self) -> Optional[State]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:State)
                WITH s.state_number AS sn
                RETURN MAX(sn) AS max_state
                """
            )
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
                states.append(
                    State(
                        state_number=s.get("state_number", 0),
                        user_prompt=s.get("user_prompt", ""),
                        branch_name=s.get("branch_name", ""),
                        git_diff_info=s.get("git_diff_info", ""),
                        hash=s.get("hash", ""),
                        created_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None,
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
            return result.single()["count"] > 0

    def count(self) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH (s:State) RETURN COUNT(s) AS count")
            return result.single()["count"]

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


class Neo4jTransitionRepository(TransitionRepository):
    def __init__(self, driver: GraphDatabase.driver, settings: Settings) -> None:
        self.driver = driver
        self.settings = settings

    def create(self, transition: Transition) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:State {state_number: $current_state})
                MATCH (to:State {state_number: $next_state})
                CREATE (from)-[t:TRANSITION {
                    transition_id: $transition_id,
                    user_prompt: $user_prompt,
                    timestamp: $timestamp
                }]->(to)
                RETURN t
                """,
                transition_id=str(transition.transition_id),
                current_state=transition.current_state,
                next_state=transition.next_state,
                user_prompt=transition.user_prompt,
                timestamp=transition.timestamp.isoformat() if transition.timestamp else None,
            )
            return result.single() is not None

    def get_by_id(self, transition_id: UUID) -> Optional[Transition]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH ()-[t:TRANSITION {transition_id: $transition_id}]->()
                RETURN t
                """,
                transition_id=str(transition_id),
            )
            record = result.single()
            if record:
                t = record["t"]
                return Transition(
                    transition_id=UUID(t.get("transition_id", "")),
                    current_state=0,
                    next_state=0,
                    user_prompt=t.get("user_prompt"),
                    timestamp=datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else None,
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
                            transition_id=UUID(t.get("transition_id", "")),
                            current_state=record["current_state"],
                            next_state=record["next_state"],
                            user_prompt=t.get("user_prompt"),
                            timestamp=datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else None,
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
                        transition_id=UUID(t.get("transition_id", "")),
                        current_state=0,
                        next_state=0,
                        user_prompt=t.get("user_prompt"),
                        timestamp=datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else None,
                    )
                )
            return transitions

    def count(self) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH ()-[t:TRANSITION]->() RETURN COUNT(t) AS count")
            return result.single()["count"]


def create_neo4j_repositories(
    uri: str, user: str, password: str, settings: Settings
) -> tuple[Neo4jStateRepository, Neo4jTransitionRepository]:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return Neo4jStateRepository(driver, settings), Neo4jTransitionRepository(driver, settings)
