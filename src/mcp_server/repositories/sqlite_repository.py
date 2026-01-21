from typing import List, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from ..models.state_model import State, Transition
from ..repositories.abstract_repositories import StateRepository, TransitionRepository
from ..config import Settings

Base = declarative_base()


class StateModel(Base):
    __tablename__ = "states"
    state_number = Column(Integer, primary_key=True)
    user_prompt = Column(Text, nullable=False)
    branch_name = Column(String(255), nullable=False)
    git_diff_info = Column(Text, nullable=True)
    hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TransitionModel(Base):
    __tablename__ = "transitions"
    id = Column(String(36), primary_key=True)
    current_state = Column(Integer, nullable=False)
    next_state = Column(Integer, nullable=False)
    user_prompt = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class SQLiteStateRepository(StateRepository):
    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    def create(self, state: State) -> bool:
        session = self.session_factory()
        try:
            existing = session.query(StateModel).filter_by(hash=state.hash).first()
            if existing:
                return True
            state_model = StateModel(
                state_number=state.state_number,
                user_prompt=state.user_prompt,
                branch_name=state.branch_name,
                git_diff_info=state.git_diff_info,
                hash=state.hash,
                created_at=state.created_at,
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
                return State(
                    state_number=state_model.state_number,
                    user_prompt=state_model.user_prompt,
                    branch_name=state_model.branch_name,
                    git_diff_info=state_model.git_diff_info,
                    hash=state_model.hash,
                    created_at=state_model.created_at,
                )
            return None
        finally:
            session.close()

    def get_current(self) -> Optional[State]:
        session = self.session_factory()
        try:
            state_model = session.query(StateModel).order_by(StateModel.state_number.desc()).first()
            if state_model:
                return State(
                    state_number=state_model.state_number,
                    user_prompt=state_model.user_prompt,
                    branch_name=state_model.branch_name,
                    git_diff_info=state_model.git_diff_info,
                    hash=state_model.hash,
                    created_at=state_model.created_at,
                )
            return None
        finally:
            session.close()

    def get_all(self) -> List[State]:
        session = self.session_factory()
        try:
            state_models = session.query(StateModel).order_by(StateModel.state_number).all()
            return [
                State(
                    state_number=sm.state_number,
                    user_prompt=sm.user_prompt,
                    branch_name=sm.branch_name,
                    git_diff_info=sm.git_diff_info,
                    hash=sm.hash,
                    created_at=sm.created_at,
                )
                for sm in state_models
            ]
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
            results = session.query(StateModel).filter(
                StateModel.user_prompt.contains(text)
            ).all()
            return [sm.state_number for sm in results]
        finally:
            session.close()


class SQLiteTransitionRepository(TransitionRepository):
    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    def create(self, transition: Transition) -> bool:
        session = self.session_factory()
        try:
            existing = session.query(TransitionModel).filter_by(id=str(transition.transition_id)).first()
            if existing:
                return True
            transition_model = TransitionModel(
                id=str(transition.transition_id),
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

    def get_by_id(self, transition_id: UUID) -> Optional[Transition]:
        session = self.session_factory()
        try:
            tm = session.query(TransitionModel).filter_by(id=str(transition_id)).first()
            if tm:
                return Transition(
                    transition_id=UUID(tm.id),
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
                    transition_id=UUID(tm.id),
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
            tm_models = session.query(TransitionModel).order_by(
                TransitionModel.timestamp.desc()
            ).limit(limit).all()
            return [
                Transition(
                    transition_id=UUID(tm.id),
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
    return SQLiteStateRepository(session_factory, settings), SQLiteTransitionRepository(session_factory, settings)
