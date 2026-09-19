# conftest.py — shared fixtures for the Python integration suite.
#
# These tests run with NO hardware: the DeviceManager is used with the
# "dummy" transport, so every deck operation exercises the real library code
# path (encode/render/transport writes) while the USB layer is stubbed.

from __future__ import annotations

import pytest


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Point STREAMDECK_DB at a fresh SQLite file for this test."""
    db_file = tmp_path / "test-streamdeck.db"
    monkeypatch.setenv("STREAMDECK_DB", str(db_file))
    # db.py reads the env var at import time; reload to pick the new path.
    # models/app are NOT reloaded (single declarative metadata across tests).
    import importlib

    from streamdeck import db

    importlib.reload(db)
    yield db_file
    db.engine.dispose()


@pytest.fixture()
def dummy_transport(monkeypatch):
    """Force the dummy transport for the duration of a test."""
    monkeypatch.setenv("STREAMDECK_TRANSPORT", "dummy")
    yield
    monkeypatch.delenv("STREAMDECK_TRANSPORT", raising=False)


@pytest.fixture()
def client(tmp_db, dummy_transport):
    """FastAPI TestClient wired to a temp DB + the dummy transport."""
    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    from streamdeck.db import engine
    from streamdeck.models import StreamDeckConfig, StreamDeckDevice  # noqa: F401

    SQLModel.metadata.create_all(engine)

    from streamdeck.app import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def dummy_deck(dummy_transport):
    """A single opened StreamDeck driven through the dummy transport."""
    from streamdeck.core.DeviceManager import DeviceManager

    manager = DeviceManager(transport="dummy")
    decks = manager.enumerate()
    assert decks, "dummy transport must enumerate decks"
    deck = decks[0]
    deck.open()
    yield deck
    deck.close()
