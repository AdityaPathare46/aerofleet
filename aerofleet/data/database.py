"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from aerofleet.utils.logging import get_logger
from aerofleet.utils.config import get_config
from aerofleet.data.models.models import Base

logger = get_logger(__name__)

# Global engine and session factory
_engine = None
_SessionLocal = None


def init_db():
    """Initialize database engine and create tables."""
    global _engine, _SessionLocal

    config = get_config()

    logger.info(f"Initializing database: {config.database.database_url}")

    if config.database.database_url == "sqlite:///:memory:":
        # In-memory SQLite is one database *per connection* by default. The
        # pool_size/max_overflow kwargs below force QueuePool (multiple
        # connections → each sees a blank DB); the SQLAlchemy default
        # SingletonThreadPool doesn't accept those kwargs at all. StaticPool
        # keeps every session on the single connection that actually has
        # the schema — needed for tests/conftest.py's isolated in-memory DB.
        _engine = create_engine(
            config.database.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=config.database.echo,
        )
    else:
        _engine = create_engine(
            config.database.database_url,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            echo=config.database.echo
        )

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Create tables
    Base.metadata.create_all(bind=_engine)

    logger.info("Database initialized successfully")


def get_db_engine():
    """Get database engine."""
    if _engine is None:
        init_db()
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session as context manager.
    
    Usage:
        with get_db_session() as db:
            mission = db.query(Mission).first()
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()
