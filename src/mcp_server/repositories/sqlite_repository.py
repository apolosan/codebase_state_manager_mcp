import json
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from ..utils.hash import generate_state_hash

if TYPE_CHECKING:
    from sqlalchemy.orm.decl_api import DeclarativeMeta

from ..config import Settings
from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository

Base = declarative_base()


class StateModel(Base):
    __tablename__ = "states"
    state_number = Column(Integer, primary_key=True)
    user_prompt = Column(Text, nullable=False)
    branch_name = Column(String(255), nullable=False)
    git_diff_info = Column(Text, nullable=True)
    hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    file_hashes = Column(Text, nullable=True)
    file_hash_deltas = Column(Text, nullable=True)


class TransitionModel(Base):
    __tablename__ = "transitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    current_state = Column(Integer, nullable=False)
    next_state = Column(Integer, nullable=False)
    user_prompt = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class SQLiteStateRepository(StateRepository):
    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self._engine = None

    def close(self) -> None:
        """Close the database connection."""
        pass

    def create(self, state: State) -> bool:
        session = self.session_factory()
        try:
            existing = session.query(StateModel).filter_by(hash=state.hash).first()
            if existing:
                return True
            file_hashes_json = json.dumps(state.file_hashes) if state.file_hashes else None
            file_hash_deltas_json = (
                json.dumps(state.file_hash_deltas) if state.file_hash_deltas else None
            )
            state_model = StateModel(
                state_number=state.state_number,
                user_prompt=state.user_prompt,
                branch_name=state.branch_name,
                git_diff_info=state.git_diff_info,
                hash=state.hash,
                created_at=state.created_at,
                file_hashes=file_hashes_json,
                file_hash_deltas=file_hash_deltas_json,
            )
            session.add(state_model)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def get_by_number(self, state_number: int) -> Optional[State]:
        session = self.session_factory()
        try:
            state_model = session.query(StateModel).filter_by(state_number=state_number).first()
            if state_model:
                file_hashes = {}
                if state_model.file_hashes:
                    try:
                        file_hashes = json.loads(state_model.file_hashes)
                    except json.JSONDecodeError:
                        file_hashes = {}
                return State(
                    state_number=state_model.state_number,
                    user_prompt=state_model.user_prompt,
                    branch_name=state_model.branch_name,
                    git_diff_info=state_model.git_diff_info,
                    hash=state_model.hash,
                    created_at=state_model.created_at,
                    file_hashes=file_hashes,
                )
            return None
        finally:
            session.close()

    def get_current(self) -> Optional[State]:
        session = self.session_factory()
        try:
            state_model = session.query(StateModel).order_by(StateModel.state_number.desc()).first()
            if state_model:
                file_hashes = {}
                if state_model.file_hashes:
                    try:
                        file_hashes = json.loads(state_model.file_hashes)
                    except json.JSONDecodeError:
                        file_hashes = {}
                return State(
                    state_number=state_model.state_number,
                    user_prompt=state_model.user_prompt,
                    branch_name=state_model.branch_name,
                    git_diff_info=state_model.git_diff_info,
                    hash=state_model.hash,
                    created_at=state_model.created_at,
                    file_hashes=file_hashes,
                )
            return None
        finally:
            session.close()

    def get_all(self) -> List[State]:
        session = self.session_factory()
        try:
            state_models = session.query(StateModel).order_by(StateModel.state_number).all()
            states = []
            for sm in state_models:
                file_hashes = {}
                if sm.file_hashes:
                    try:
                        file_hashes = json.loads(sm.file_hashes)
                    except json.JSONDecodeError:
                        file_hashes = {}
                file_hash_deltas = {}
                if sm.file_hash_deltas:
                    try:
                        file_hash_deltas = json.loads(sm.file_hash_deltas)
                    except json.JSONDecodeError:
                        file_hash_deltas = {}
                states.append(
                    State(
                        state_number=sm.state_number,
                        user_prompt=sm.user_prompt,
                        branch_name=sm.branch_name,
                        git_diff_info=sm.git_diff_info,
                        hash=sm.hash,
                        created_at=sm.created_at,
                        file_hashes=file_hashes if file_hashes else None,
                        file_hash_deltas=file_hash_deltas,
                    )
                )
            return states
        finally:
            session.close()

    def exists(self, state_number: int) -> bool:
        session = self.session_factory()
        try:
            return session.query(StateModel).filter_by(state_number=state_number).count() > 0
        finally:
            session.close()

    def count(self) -> int:
        session = self.session_factory()
        try:
            return session.query(StateModel).count()
        finally:
            session.close()

    def search(self, text: str) -> List[int]:
        session = self.session_factory()
        try:
            results = session.query(StateModel).filter(StateModel.user_prompt.contains(text)).all()
            return [sm.state_number for sm in results]
        finally:
            session.close()

    def delete(self, state_number: int) -> bool:
        session = self.session_factory()
        try:
            result = session.query(StateModel).filter_by(state_number=state_number).delete()
            session.commit()
            return result > 0
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def create_next(self, state: State) -> bool:
        """Create a new state with the next sequential state number."""
        session = self.session_factory()
        try:
            # Acquire exclusive lock to prevent race conditions
            session.execute("BEGIN IMMEDIATE")

            # Get current maximum state number
            max_state = session.query(func.max(StateModel.state_number)).scalar()
            next_state_number = (max_state + 1) if max_state is not None else 0

            # Check if state with this number already exists (should not happen with lock)
            existing = session.query(StateModel).filter_by(state_number=next_state_number).first()
            if existing:
                session.rollback()
                return False

            # Update the state object with the new number
            state.state_number = next_state_number

            # Generate hash with the correct state number
            state.hash = generate_state_hash(
                state.user_prompt,
                state.branch_name,
                state.git_diff_info,
                state.state_number,
            )

            # Convert file hashes to JSON
            file_hashes_json = json.dumps(state.file_hashes) if state.file_hashes else None
            file_hash_deltas_json = (
                json.dumps(state.file_hash_deltas) if state.file_hash_deltas else None
            )

            # Create model and persist
            state_model = StateModel(
                state_number=state.state_number,
                user_prompt=state.user_prompt,
                branch_name=state.branch_name,
                git_diff_info=state.git_diff_info,
                hash=state.hash,
                created_at=state.created_at,
                file_hashes=file_hashes_json,
                file_hash_deltas=file_hash_deltas_json,
            )
            session.add(state_model)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()


class SQLiteTransitionRepository(TransitionRepository):
    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    def close(self) -> None:
        """Close the database connection."""
        pass

    def create(self, transition: Transition) -> bool:
        session = self.session_factory()
        try:
            existing = session.query(TransitionModel).filter_by(id=transition.transition_id).first()
            if existing:
                return True
            transition_model = TransitionModel(
                id=transition.transition_id,
                current_state=transition.current_state,
                next_state=transition.next_state,
                user_prompt=transition.user_prompt,
                timestamp=transition.timestamp,
            )
            session.add(transition_model)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def create_next(self, transition: Transition) -> bool:
        """Create a new transition with the next sequential transition ID."""
        session = self.session_factory()
        try:
            # Acquire exclusive lock to prevent race conditions
            session.execute("BEGIN IMMEDIATE")

            # Get current maximum transition ID
            max_id = session.query(func.max(TransitionModel.id)).scalar()
            next_id = (max_id + 1) if max_id is not None else 1

            # Check if transition with this ID already exists (should not happen with lock)
            existing = session.query(TransitionModel).filter_by(id=next_id).first()
            if existing:
                session.rollback()
                return False

            # Update the transition object with the new ID
            transition.transition_id = next_id

            # Create model and persist
            transition_model = TransitionModel(
                id=transition.transition_id,
                current_state=transition.current_state,
                next_state=transition.next_state,
                user_prompt=transition.user_prompt,
                timestamp=transition.timestamp,
            )
            session.add(transition_model)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def get_by_id(self, transition_id: int) -> Optional[Transition]:
        session = self.session_factory()
        try:
            tm = session.query(TransitionModel).filter_by(id=transition_id).first()
            if tm:
                return Transition(
                    transition_id=tm.id,
                    current_state=tm.current_state,
                    next_state=tm.next_state,
                    user_prompt=tm.user_prompt,
                    timestamp=tm.timestamp,
                )
            return None
        finally:
            session.close()

    def get_by_state(self, state_number: int) -> List[Transition]:
        session = self.session_factory()
        try:
            tm_models = session.query(TransitionModel).filter_by(current_state=state_number).all()
            return [
                Transition(
                    transition_id=tm.id,
                    current_state=tm.current_state,
                    next_state=tm.next_state,
                    user_prompt=tm.user_prompt,
                    timestamp=tm.timestamp,
                )
                for tm in tm_models
            ]
        finally:
            session.close()

    def get_last(self, limit: int) -> List[Transition]:
        session = self.session_factory()
        try:
            tm_models = (
                session.query(TransitionModel)
                .order_by(TransitionModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                Transition(
                    transition_id=tm.id,
                    current_state=tm.current_state,
                    next_state=tm.next_state,
                    user_prompt=tm.user_prompt,
                    timestamp=tm.timestamp,
                )
                for tm in tm_models
            ]
        finally:
            session.close()

    def count(self) -> int:
        session = self.session_factory()
        try:
            return session.query(TransitionModel).count()
        finally:
            session.close()


def create_sqlite_engine(path: str):
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def create_sqlite_repositories(
    path: str, settings: Settings
) -> tuple[SQLiteStateRepository, SQLiteTransitionRepository]:
    engine = create_sqlite_engine(path)
    session_factory = sessionmaker(bind=engine)
    return SQLiteStateRepository(session_factory, settings), SQLiteTransitionRepository(
        session_factory, settings
    )
