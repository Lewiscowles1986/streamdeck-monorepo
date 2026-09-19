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