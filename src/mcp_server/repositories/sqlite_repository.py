import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from ..utils.hash import generate_state_hash
from ..utils.retry import retry_on_lock

logger = logging.getLogger(__name__)

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


class MetadataModel(Base):
    __tablename__ = "metadata"
    key = Column(String(255), primary_key=True)
    value = Column(String(255), nullable=False)


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
            metadata = session.query(MetadataModel).filter_by(key="current_state").first()
            if metadata:
                state_number = int(metadata.value)
                return self.get_by_number(state_number)

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

    @retry_on_lock(max_retries=5)
    def create_next(self, state: State) -> bool:
        """Create a new state with the next sequential state number.

        Returns:
            bool: True if state created successfully, False otherwise.

        Logs:
            - ERROR: SQLite lock contention (OperationalError)
            - ERROR: Any other database exception with full traceback
        """
        from sqlalchemy import text

        session = self.session_factory()
        next_state_number = None  # Initialize for error logging
        try:
            session.execute(text("BEGIN IMMEDIATE"))

            max_state = session.query(func.max(StateModel.state_number)).scalar()
            next_state_number = (max_state + 1) if max_state is not None else 0

            existing = session.query(StateModel).filter_by(state_number=next_state_number).first()
            if existing:
                logger.warning(
                    f"State {next_state_number} already exists. "
                    f"Possible race condition or failed previous transaction."
                )
                session.rollback()
                return False

            state.state_number = next_state_number

            state.hash = generate_state_hash(
                state.user_prompt,
                state.branch_name,
                state.git_diff_info,
                state.state_number,
            )

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
            logger.info(f"Successfully created state {state.state_number}")
            return True
        except OperationalError as e:
            session.rollback()
            error_msg = str(e)
            state_info = (
                f"state {next_state_number}" if next_state_number is not None else "new state"
            )
            if "database is locked" in error_msg.lower():
                logger.error(
                    f"SQLite database locked when creating {state_info}. "
                    f"Another process may be holding a lock. Error: {error_msg}"
                )
            else:
                logger.error(
                    f"SQLite operational error creating {state_info}: {error_msg}", exc_info=True
                )
            return False
        except Exception as e:
            session.rollback()
            state_info = (
                f"state {next_state_number}" if next_state_number is not None else "new state"
            )
            logger.error(
                f"Unexpected error creating {state_info}: {type(e).__name__}: {e}", exc_info=True
            )
            return False
        finally:
            session.close()

    @retry_on_lock(max_retries=5)
    def set_current(self, state_number: int) -> bool:
        """Set the current state explicitly for arbitrary transitions.

        Args:
            state_number: The state number to set as current.

        Returns:
            bool: True if updated successfully, False otherwise.

        Logs:
            - WARNING: State does not exist
            - ERROR: Database exceptions with full traceback
        """
        session = self.session_factory()
        try:
            state_exists = session.query(StateModel).filter_by(state_number=state_number).first()
            if not state_exists:
                logger.warning(
                    f"Cannot set current to state {state_number}: state does not exist in database"
                )
                return False

            session.query(MetadataModel).filter_by(key="current_state").delete()
            metadata = MetadataModel(key="current_state", value=str(state_number))
            session.add(metadata)
            session.commit()
            logger.info(f"Successfully set current state to {state_number}")
            return True
        except OperationalError as e:
            session.rollback()
            logger.error(
                f"SQLite operational error setting current state to {state_number}: {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            session.rollback()
            logger.error(
                f"Unexpected error setting current state to {state_number}: {type(e).__name__}: {e}",
                exc_info=True,
            )
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

    @retry_on_lock(max_retries=5)
    def create_next(self, transition: Transition) -> bool:
        """Create a new transition with the next sequential transition ID.

        Returns:
            bool: True if transition created successfully, False otherwise.

        Logs:
            - ERROR: SQLite lock contention (OperationalError)
            - ERROR: Any other database exception with full traceback
        """
        from sqlalchemy import text

        session = self.session_factory()
        next_id = None  # Initialize for error logging
        try:
            session.execute(text("BEGIN IMMEDIATE"))

            max_id = session.query(func.max(TransitionModel.id)).scalar()
            next_id = (max_id + 1) if max_id is not None else 1

            existing = session.query(TransitionModel).filter_by(id=next_id).first()
            if existing:
                logger.warning(
                    f"Transition {next_id} already exists. "
                    f"Possible race condition or failed previous transaction."
                )
                session.rollback()
                return False

            transition.transition_id = next_id

            transition_model = TransitionModel(
                id=transition.transition_id,
                current_state=transition.current_state,
                next_state=transition.next_state,
                user_prompt=transition.user_prompt,
                timestamp=transition.timestamp,
            )
            session.add(transition_model)
            session.commit()
            logger.info(
                f"Successfully created transition {transition.transition_id} "
                f"({transition.current_state} → {transition.next_state})"
            )
            return True
        except OperationalError as e:
            session.rollback()
            error_msg = str(e)
            trans_info = f"transition {next_id}" if next_id is not None else "new transition"
            if "database is locked" in error_msg.lower():
                logger.error(
                    f"SQLite database locked when creating {trans_info}. "
                    f"Another process may be holding a lock. Error: {error_msg}"
                )
            else:
                logger.error(
                    f"SQLite operational error creating {trans_info}: {error_msg}", exc_info=True
                )
            return False
        except Exception as e:
            session.rollback()
            trans_info = f"transition {next_id}" if next_id is not None else "new transition"
            logger.error(
                f"Unexpected error creating {trans_info}: {type(e).__name__}: {e}", exc_info=True
            )
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
