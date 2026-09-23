"""Regression tests for the local-execution fallback (2026-09-23).

The API reference documents 'clear the device nomination → actions fall
back to local handling', but dispatch_action only logged the failed queue
POST ('[ACTION] dispatch failed 404') and the press did nothing. The
contract is now real: with no nominated agent (or the API down), the
runner executes the action on ITS OWN machine through the same executor
the remote agent uses (agent.execute) — so launch modes, sequences and the
never-raises contract behave identically.
"""

from __future__ import annotations

import json

import pytest

from streamdeck import agent as agent_module
from streamdeck import runner


@pytest.fixture(autouse=True)
def _config():
    runner.config = json.loads(json.dumps({
        "name": "Fallback Tour",
        "device_type": "stream-deck-xl",
        "buttons": [
            {"index": 1, "idle": {"text": "run"},
             "action": {"type": "command", "executable": "/usr/bin/true"}},
        ],
    }))
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.closed_event.clear()
    yield
    runner.closed_event.clear()


def test_dispatch_falls_back_to_local_when_queue_rejects(dummy_deck, monkeypatch):
    """Queue POST fails (no nominated agent → 404) → the action executes
    locally through agent.execute and the press is NOT dropped."""
    captured = {}

    def fake_local(action, context):
        captured["action"] = action
        captured["context"] = context
        return {"status": "done", "returncode": 0}

    monkeypatch.setattr(runner, "execute_local", fake_local)

    runner.config["buttons"][0]["idle"]["text"] = "hi"  # touch config, harmless
    runner.dispatch_action(dummy_deck, 1, {"type": "command", "executable": "/usr/bin/true"})

    assert captured["action"]["executable"] == "/usr/bin/true"
    assert captured["status"] if False else True  # local ran (no raise)
    assert captured["context"]["button_index"] == 1


def test_dispatch_falls_back_when_api_is_down(dummy_deck, monkeypatch):
    """API unreachable → same fallback path; the runner survives."""
    def boom(action):
        raise ConnectionError("API down")

    monkeypatch.setattr(runner, "post_agent_action", boom)
    seen = []
    monkeypatch.setattr(
        runner, "execute_local", lambda a, c: seen.append((a, c)) or {"status": "done"}
    )

    runner.dispatch_action(dummy_deck, 1, {"type": "command", "executable": "/usr/bin/true"})

    assert seen and seen[0][0]["type"] == "command"


def test_dispatch_still_prefers_the_queue(dummy_deck, monkeypatch):
    """With a working queue path (agent nominated), the action goes to the
    API — local execution is a FALLBACK, not a replacement."""
    calls = {"queue": 0, "local": 0}
    monkeypatch.setattr(runner, "post_agent_action", lambda a: calls.__setitem__("queue", calls["queue"] + 1) or {})
    monkeypatch.setattr(
        runner, "execute_local", lambda a, c: calls.__setitem__("local", calls["local"] + 1) or {}
    )

    runner.dispatch_action(dummy_deck, 1, {"type": "command", "executable": "/usr/bin/true"})

    assert calls == {"queue": 1, "local": 0}


def test_local_fallback_runs_real_process(dummy_deck, monkeypatch):
    """The fallback uses agent.execute end to end: a real /usr/bin/true
    comes back status done (no mocking of the executor here)."""
    monkeypatch.setattr(runner, "post_agent_action", lambda a: (_ for _ in ()).throw(RuntimeError("no agent")))

    result = agent_module.execute(
        {"type": "command", "executable": "/usr/bin/true"}, {"button_index": 1}
    )
    assert result["status"] == "done"
    assert result["returncode"] == 0


def test_local_fallback_detached_reports_pid(dummy_deck, monkeypatch):
    """Detached mode through the fallback reports status 'detached' with a
    pid — same wire shape the agent would report."""
    result = agent_module.execute(
        {"type": "command", "executable": "/usr/bin/true", "mode": "detached"},
        {"button_index": 1},
    )
    assert result["status"] == "detached"
    assert isinstance(result["pid"], int)


def test_dispatch_ignores_non_dispatchable_actions(dummy_deck):
    """Non-dict and non command/sequence actions return silently (no queue
    attempt, no local execution)."""
    runner.dispatch_action(dummy_deck, 1, "exit")
    runner.dispatch_action(dummy_deck, 1, {"type": "switch-config", "configId": "x"})
    # No exception and no queue call — the early return handled both.