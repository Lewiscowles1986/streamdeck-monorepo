"""Regression tests for the assign-and-run fixes (2026-09-23, config-driven
real-hardware tour). Two bugs found while driving the real XL through the
CLI with an API-assigned config:

1. Ordering: main() ran the device-type gate BEFORE any config was loaded
   (the module default {}), because run_deck only fetches the assigned
   config after the gate. On the assign-and-run path (no --config file) the
   gate compared against "" and rejected every deck. Fixed by fetching the
   assigned config in main() before the gate; an empty device_type means
   "no pin" (run any attached deck).

2. Dialect ownership: the REST API serves camelCase (`deviceType`); the
   runner's internal format is snake_case (`device_type`). Per the operator
   ruling — "the API storage format should not dictate the CLI runner
   format" — translation lives at the API BOUNDARY
   (app.to_runner_format), not in the runner core. The runner core never
   sees the wire dialect.
"""

from __future__ import annotations

import argparse

from streamdeck import app as app_module
from streamdeck import runner


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        config=None,
        brightness=30,
        list_devices=False,
        device_type=None,
        ignore_device_type_check=False,
        api="http://localhost:8000",
        device_id=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_device_type_gate_honors_snake_case_file_configs(dummy_deck, monkeypatch):
    """The --config file dialect (device_type) passes the gate."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "hi"}}],
    }
    monkeypatch.setattr(runner, "fetch_assigned_config", lambda api, device_id: None)

    opened = []
    monkeypatch.setattr(dummy_deck, "reset", lambda: opened.append("reset"))

    runner.closed_event.set()
    runner.run_deck(dummy_deck, _args())

    assert opened == ["reset"]


def test_empty_device_type_runs_any_attached_deck(dummy_deck, monkeypatch):
    """A config with no device_type pin (or an empty one) matches any deck:
    the old gate treated '' as matching-nothing and skipped every deck."""
    runner.config = {"buttons": [{"index": 0, "idle": {"text": "hi"}}]}
    monkeypatch.setattr(runner, "fetch_assigned_config", lambda api, device_id: None)

    opened = []
    monkeypatch.setattr(dummy_deck, "reset", lambda: opened.append("reset"))

    runner.closed_event.set()
    runner.run_deck(dummy_deck, _args())

    assert opened == ["reset"]


def test_main_fetches_assigned_config_before_device_gate(dummy_deck, monkeypatch):
    """Regression for the ordering bug: with no --config file, main() must
    fetch the API-assigned config BEFORE the device-type gate, else the gate
    sees the empty module config and skips every deck."""
    assigned = {
        "device_type": "stream-deck-xl",  # post-boundary (snake_case) shape
        "name": "Tour 1",
        "buttons": [{"index": 0, "idle": {"text": "hi"}}],
    }

    monkeypatch.setattr(
        runner, "fetch_assigned_config", lambda api, device_id: assigned
    )

    class _Watcher:
        def __init__(self, *a, **k):
            self.thread = None

        def start(self):
            pass

    monkeypatch.setattr(runner, "TriggerWatcher", _Watcher)

    opened = []
    monkeypatch.setattr(dummy_deck, "reset", lambda: opened.append("reset"))

    class _FakeManager:
        def enumerate(self):
            return [dummy_deck]

    monkeypatch.setattr(app_module, "get_device_manager", lambda: _FakeManager())

    runner.main(_args(device_id=dummy_deck.get_serial_number()))

    assert opened == ["reset"], (
        "main() skipped the deck: assigned config was not loaded before the "
        "device-type gate"
    )


def test_api_boundary_translates_camelcase_to_runner_format():
    """The DIALECT test lives here, at the boundary — not in the runner
    core. to_runner_format must turn the API's aliased deviceType into the
    runner's device_type and pass everything else through untouched."""
    api_shape = {
        "id": "abc",
        "name": "Tour 1",
        "deviceType": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "hi"}}],
        "triggers": None,
    }
    out = app_module.to_runner_format(api_shape)
    assert out["device_type"] == "stream-deck-xl"
    assert "deviceType" not in out
    assert out["buttons"] == api_shape["buttons"]  # pass-through
    assert out["id"] == "abc"  # unknown keys survive


def test_runner_core_is_dialect_free():
    """The runner core must NOT know wire dialects: no `deviceType` reads
    anywhere in runner.py — translation happened upstream at the API
    boundary. Pins the architecture against future core-side dialect
    fallbacks."""
    import inspect

    source = inspect.getsource(runner)
    assert '"deviceType"' not in source, (
        "runner core reads the API wire dialect directly — translate at the "
        "API boundary (app.to_runner_format) instead"
    )


def test_assigned_config_end_to_end_through_boundary(client):
    """Full chain over REST: create config (camelCase in), assign to a
    device, GET /device/{id}/config — the config the runner receives must
    be in runner format (device_type) and carry the buttons."""
    created = client.post(
        "/config",
        json={
            "name": "Dialect Tour",
            "deviceType": "stream-deck-xl",
            "buttons": [{"index": 0, "idle": {"text": "hi"}}],
        },
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    devices = client.get("/devices").json()
    device_id = devices[0]["id"]
    assert client.put(f"/device/{device_id}/config/{cid}").status_code == 200

    served = client.get(f"/device/{device_id}/config").json()["config"]
    assert served["device_type"] == "stream-deck-xl"
    assert "deviceType" not in served
    assert served["buttons"] == [{"index": 0, "idle": {"text": "hi"}}]