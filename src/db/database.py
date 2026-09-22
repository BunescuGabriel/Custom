import logging
from collections.abc import Generator
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import BASE_DIR, DATABASE_PATH, DATABASE_URL

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_database_ready = False


def init_db() -> None:
    global _database_ready
    if _database_ready:
        return

    alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.attributes["configure_logger"] = False
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception:
        logger.exception("database_initialization_failed path=%s", DATABASE_PATH)
        raise
    _database_ready = True
    logger.info("database_ready path=%s", DATABASE_PATH)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
