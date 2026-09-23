import logging
from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock

from alembic import command
from alembic.config import Config
from filelock import FileLock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import BASE_DIR, DATA_DIR, DATABASE_PATH, DATABASE_URL

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _configure_sqlite(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_database_ready = False
_initialization_lock = Lock()


def init_db() -> None:
    global _database_ready
    if _database_ready:
        return

    with _initialization_lock:
        if _database_ready:
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with FileLock(str(DATA_DIR / "migration.lock"), timeout=30):
            alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
            alembic_cfg.attributes["configure_logger"] = False
            alembic_cfg.attributes["database_url"] = DATABASE_URL
            try:
                command.upgrade(alembic_cfg, "head")
                with engine.connect() as connection:
                    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                    if violations:
                        logger.error("database_broken_links rows=%s", violations)
            except Exception:
                logger.exception("database_initialization_failed path=%s", DATABASE_PATH)
                raise
        _database_ready = True
        logger.info("database_ready path=%s", DATABASE_PATH)


@contextmanager
def get_session() -> Generator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
