# db.py — SQLite engine/session (SQLModel)
# Ported from streamdeck/api/db.py @ 078b8b23 (repo streamdeck, main).

from contextlib import contextmanager
import os

from sqlmodel import create_engine, Session, SQLModel

DB_FILE = os.getenv("STREAMDECK_DB", "streamdeck.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# For SQLite with multiple threads in FastAPI, check_same_thread=False
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@contextmanager
def get_session():
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Create tables if they do not exist yet (keeps the stack zero-config)."""
    from .models import StreamDeckConfig, StreamDeckDevice  # noqa: F401, PLC0415

    SQLModel.metadata.create_all(engine)
    _migrate_triggers_column()


def _migrate_triggers_column() -> None:
    """R5 (P16): older dev databases predate the `triggers` column.
    create_all only creates MISSING TABLES — a table that exists without
    the column stays broken forever. SQLite supports ADD COLUMN, so add it
    idempotently (checked via PRAGMA table_info)."""
    from sqlalchemy import text

    with engine.connect() as connection:
        columns = [
            row[1]
            for row in connection.execute(
                text("PRAGMA table_info(streamdeckconfig)")
            )
        ]
        if "triggers" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE streamdeckconfig "
                    "ADD COLUMN triggers JSON NULL"
                )
            )
            connection.commit()