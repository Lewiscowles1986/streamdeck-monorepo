# test_parity.py — frontend ↔ backend feature-parity contract tests.
#
# Every test here encodes one row of docs/parity.md: a feature the UI
# advertises (or the backend implements) that must be supported on BOTH
# sides. If one of these fails, the two surfaces have drifted apart.

from __future__ import annotations

import json

import pytest

from streamdeck import runner, agent


@pytest.fixture(autouse=True)
def clean_runner_state():
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.closed_event.clear()
    yield
    runner.closed_event.clear()


# ---------------------------------------------------------------
# Template variables: the UI inserts {{...}} tokens into action
# fields (ActionEditor + TEMPLATE_VARIABLES); the backend must
# expand them before the command runs.
# ---------------------------------------------------------------
def test_expand_template_vars_basic():
    ctx = {
        "button_index": 3,
        "device_id": "DUMMY123",
        "toggle_state": 1,
        "config_name": "Gaming",
    }
    assert (
        agent.expand_template_vars("say {{button_index}} on {{device_id}}", ctx)
        == "say 3 on DUMMY123"
    )
    assert agent.expand_template_vars("state={{toggle_state}}", ctx) == "state=1"
    assert agent.expand_template_vars("cfg={{config_name}}", ctx) == "cfg=Gaming"


def test_expand_template_vars_recurses_into_env_and_cwd():
    ctx = {"config_name": "Gaming"}
    action = {
        "type": "command",
        "executable": "/bin/{{config_name}}",
        "arguments": "--dir {{config_name}}",
        "cwd": "/tmp/{{config_name}}",
        "env": {"WELCOME": "hello {{config_name}}"},
    }
    expanded = agent.expand_template_vars(action, ctx)
    assert expanded["executable"] == "/bin/Gaming"
    assert expanded["arguments"] == "--dir Gaming"
    assert expanded["cwd"] == "/tmp/Gaming"
    assert expanded["env"]["WELCOME"] == "hello Gaming"


def test_expand_template_vars_time_tokens():
    import re

    out = agent.expand_template_vars(
        "{{timestamp}} {{date}} {{time}}", {}
    )
    ts, date, time_part = out.split(" ")
    assert re.fullmatch(r"\d+", ts)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", time_part)


def test_execute_expands_variables_with_context():
    result = agent.execute(
        {
            "type": "command",
            "executable": "echo",
            "arguments": "{{config_name}} {{button_index}}",
        },
        context={"config_name": "Parity", "button_index": 7},
    )
    assert result["status"] == "done"
    assert result["stdout"].strip() == "Parity 7"


def test_execute_still_expands_without_context():
    """Actions queued directly via the API get time tokens expanded."""
    result = agent.execute(
        {
            "type": "command",
            "executable": "echo",
            "arguments": "ts={{timestamp}}",
        }
    )
    assert result["status"] == "done"
    assert "ts=" in result["stdout"]
    assert "{{timestamp}}" not in result["stdout"]


def test_runner_dispatch_expands_button_context(dummy_deck, monkeypatch):
    """The runner knows button/device/toggle context at press time and
    must expand tokens before enqueueing the action."""
    captured: list[dict] = []
    monkeypatch.setattr(runner, "post_agent_action", lambda a: captured.append(a) or {})

    runner.config = {
        "name": "Dispatch Cfg",
        "device_type": "stream-deck-xl",
        "buttons": [
            {
                "index": 2,
                "toggleStates": [{"text": "off"}, {"text": "on"}],
                "action": {
                    "type": "command",
                    "executable": "echo",
                    "arguments": "btn={{button_index}} state={{toggle_state}} cfg={{config_name}}",
                },
            }
        ],
    }
    # Prime + press to advance the toggle to state 1.
    runner.get_button_config(2, state=True)
    runner.get_button_config(2, state=True)

    runner.dispatch_action(dummy_deck, 2, runner.config["buttons"][0]["action"])

    assert captured, "dispatch must enqueue the action"
    sent_action = captured[0]["action"]
    assert sent_action["arguments"] == f"btn=2 state=1 cfg=Dispatch Cfg"
    assert captured[0]["buttonIndex"] == 2
    assert captured[0]["deviceId"] == dummy_deck.get_serial_number()


# ---------------------------------------------------------------
# Font configuration: the UI stores font family/size/color/weight/
# position per button state; the runner must honor it when drawing.
# ---------------------------------------------------------------
def test_label_style_defaults():
    style = runner.resolve_label_style({})
    assert style["size"] == 14
    assert style["color"] == "white"
    assert style["position"] == "bottom"
    assert style["weight"] == "normal"


def test_label_style_custom():
    style = runner.resolve_label_style(
        {"font": {"size": 22, "color": "#ff0000", "position": "top", "weight": "bold"}}
    )
    assert style["size"] == 22
    assert style["color"] == "#ff0000"
    assert style["position"] == "top"
    assert style["weight"] == "bold"


def test_font_config_used_in_rendering(dummy_deck, monkeypatch):
    """update_key_image must pass the configured font style to the drawing
    call — not the hardcoded Roboto/14/white/bottom of the original port."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [
            {
                "index": 0,
                "idle": {
                    "text": "styled",
                    "font": {"size": 20, "color": "red", "position": "center"},
                },
            }
        ],
    }

    import streamdeck.runner as rmod
    from PIL import ImageDraw, ImageFont

    text_calls: list[tuple[tuple, dict]] = []
    font_calls: list[tuple] = []
    real_draw = ImageDraw.Draw
    real_font = ImageFont.truetype

    class DrawSpy:
        def __init__(self, img):
            self._real = real_draw(img)

        def text(self, *args, **kwargs):
            text_calls.append((args, kwargs))
            self._real.text(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def font_spy(path, size):
        font_calls.append((path, size))
        return real_font(path, size)

    monkeypatch.setattr(rmod.ImageDraw, "Draw", DrawSpy)
    monkeypatch.setattr(rmod.ImageFont, "truetype", font_spy)

    runner.update_key_image(dummy_deck, 0, state=False)

    assert text_calls, "label must be drawn"
    kwargs = text_calls[0][1]
    assert kwargs.get("fill") == "red"
    assert kwargs.get("anchor") == "mm"  # center position
    assert font_calls and font_calls[0][1] == 20


def test_font_position_top_and_bottom_anchors(dummy_deck, monkeypatch):
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "x"}}],
    }
    import streamdeck.runner as rmod
    from PIL import ImageDraw

    anchors: list[str] = []
    real_draw = ImageDraw.Draw

    class DrawSpy:
        def __init__(self, img):
            self._real = real_draw(img)

        def text(self, *args, **kwargs):
            anchors.append(kwargs.get("anchor"))
            self._real.text(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    monkeypatch.setattr(rmod.ImageDraw, "Draw", DrawSpy)

    # top → "ma", bottom (default) → "ms"
    runner.config["buttons"][0]["idle"]["font"] = {"position": "top"}
    runner.buttons.clear()
    runner.update_key_image(dummy_deck, 0, state=False)
    runner.config["buttons"][0]["idle"]["font"] = {"position": "bottom"}
    runner.buttons.clear()
    runner.update_key_image(dummy_deck, 0, state=False)

    assert anchors == ["ma", "ms"]


def test_font_family_resolves_to_existing_font():
    """Any advertised family must resolve to a font file that exists
    (bundled Roboto is the fallback)."""
    import pathlib

    for family in ("sans-serif", "serif", "monospace", "Roboto", "Arial", "Unknown?"):
        path = runner.resolve_font_path(family)
        assert isinstance(path, pathlib.Path)
        assert path.exists(), f"font for {family!r} must exist: {path}"


# ---------------------------------------------------------------
# Exit action: the runner treats action == "exit" as the shutdown
# button; the UI ActionEditor must be able to configure it. The
# backend contract is the string "exit" — lock it here.
# ---------------------------------------------------------------
def test_exit_action_contract_is_bare_string(dummy_deck):
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "action": "exit"}],
    }
    runner.get_button_config(0, state=False)
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.closed_event.is_set()
    assert not dummy_deck.is_open()


# ---------------------------------------------------------------
# Config deletion must not leave dangling device assignments
# (the dashboard reads currentConfigId from the device row).
# ---------------------------------------------------------------
def test_config_delete_clears_device_assignment(client):
    from streamdeck.db import engine
    from sqlmodel import Session
    from streamdeck.models import StreamDeckDevice

    device = client.get("/devices").json()[0]
    config = client.post(
        "/config",
        json={"name": "Dangling", "deviceType": "stream-deck-xl", "buttons": []},
    ).json()
    client.put(f"/device/{device['id']}/config/{config['id']}")

    client.delete(f"/config/{config['id']}")

    with Session(engine) as session:
        row = session.get(StreamDeckDevice, device["id"])
        assert row.current_config_id is None


# ---------------------------------------------------------------
# CORS: the full-stack E2E/UI serves the SPA on :8081; the API must
# answer preflights from that origin.
# ---------------------------------------------------------------
def test_cors_preflight_from_ui_port(client):
    response = client.options(
        "/devices",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") in (
        "http://localhost:8081",
        "*",
    )


def test_cors_preflight_from_ui_port_8080(client):
    response = client.options(
        "/devices",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin")


# ---------------------------------------------------------------
# Agent model dialect: the Agent model intentionally has no
# camelCase aliases (the agent CLI registers with snake_case
# last_seen). The frontend reads it accordingly — lock the dialect.
# ---------------------------------------------------------------
def test_agent_dialect_is_snake_case(client):
    client.post(
        "/agents",
        json={"id": "a1", "hostname": "box.local", "last_seen": "2026-01-01T00:00:00+0000"},
    )
    listed = client.get("/agents").json()
    assert listed[0]["hostname"] == "box.local"
    assert listed[0]["last_seen"] == "2026-01-01T00:00:00+0000"


# ---------------------------------------------------------------
# The runner-facing device config endpoint must keep returning the
# camelCase device alias fields the frontend/agent read.
# ---------------------------------------------------------------
def test_device_config_endpoint_dialect(client):
    device = client.get("/devices").json()[0]
    config = client.post(
        "/config",
        json={"name": "Dialect", "deviceType": "stream-deck-xl", "buttons": []},
    ).json()
    client.post("/agents", json={"id": "a1", "hostname": "box.local"})
    client.put(f"/device/{device['id']}/config/{config['id']}")
    client.put(f"/device/{device['id']}/agent/a1")

    payload = client.get(f"/device/{device['id']}/config").json()
    dev = payload["device"]
    assert dev["currentConfigId"] == config["id"]
    assert dev["activeAgentId"] == "a1"