# test_parity.py — frontend ↔ backend feature-parity contract tests.
#
# Every test here encodes one row of docs/parity.md: a feature the UI
# advertises (or the backend implements) that must be supported on BOTH
# sides. If one of these fails, the two surfaces have drifted apart.

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from streamdeck import runner, agent


@pytest.fixture(autouse=True)
def clean_runner_state():
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.paused_images.clear()
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


# ---------------------------------------------------------------
# Animated GIF data URIs: the UI embeds animated GIFs exactly as
# FileReader.readAsDataURL produces them; the runner must decode
# every frame once and hand back a cycle (see persistent_images).
# ---------------------------------------------------------------
# ---------------------------------------------------------------
# Round 2 (config-editor parity): command action timeout/env dialect,
# font config flowing into the rendered label, and toggle-state
# context expansion over a full action dict.
# ---------------------------------------------------------------
def test_command_action_timeout_env_dialect():
    """The queue payload must preserve the ActionEditor's timeout and env
    fields verbatim (P8: timeout is configurable AND honored)."""
    action = {
        "type": "command",
        "executable": "x",
        "arguments": "echo hi",
        "timeout": 90,
        "env": {"A": "b"},
    }
    wrapped = agent.build_agent_action(action, device_id="DUM", button_index=4)
    assert wrapped["action"]["timeout"] == 90
    assert wrapped["action"]["env"] == {"A": "b"}
    assert wrapped["action"]["arguments"] == "echo hi"
    assert wrapped["buttonIndex"] == 4
    assert wrapped["deviceId"] == "DUM"


def test_font_style_flows_into_rendered_label(dummy_deck, monkeypatch):
    """render_key_image (the runner entry point for a rendered state) must
    pass the UI's font config into the actual draw call: color, size and
    the top-position anchor."""
    import base64
    import io
    import streamdeck.runner as rmod
    from PIL import Image, ImageDraw, ImageFont

    # 8x8 solid-color PNG, inline — no fixture file needed.
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="PNG")
    png_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    style = runner.resolve_label_style(
        {"font": {"family": "serif", "size": 20, "color": "#00ff00", "position": "top"}}
    )

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

    runner.render_key_image(dummy_deck, png_uri, "HI", style)

    assert text_calls, "label must be drawn"
    kwargs = text_calls[0][1]
    assert kwargs.get("fill") == "#00ff00"
    assert kwargs.get("anchor") == "ma"  # top position
    assert font_calls and font_calls[0][1] == 20


def test_toggle_state_context_expands_in_action():
    """expand_template_vars must expand every field of a full CommandAction
    dict given the runner's press-time context — including env values."""
    ctx = {
        "button_index": 3,
        "device_id": "DUM",
        "toggle_state": 1,
        "config_name": "My Config",
    }
    action = {
        "type": "command",
        "executable": "run {{button_index}}",
        "arguments": "--state {{toggle_state}}",
        "cwd": "/tmp/{{config_name}}",
        "env": {"DEV_ID": "{{device_id}}"},
        "timeout": 45,
    }
    expanded = agent.expand_template_vars(action, ctx)
    assert expanded == {
        "type": "command",
        "executable": "run 3",
        "arguments": "--state 1",
        "cwd": "/tmp/My Config",
        "env": {"DEV_ID": "DUM"},
        "timeout": 45,
    }


def test_animated_data_uri_from_frontend_pipeline_decodes_to_frames(dummy_deck):
    import base64
    from pathlib import Path

    gif_bytes = (
        Path(__file__).resolve().parents[1] / "e2e" / "assets" / "red-blue.gif"
    ).read_bytes()
    source = f"data:image/gif;base64,{base64.b64encode(gif_bytes).decode('ascii')}"

    rendered = runner.render_key_image(dummy_deck, source)
    assert isinstance(rendered, Iterator), (
        "an animated data URI must render as a frame iterator (cycle)"
    )
    assert rendered is runner.persistent_images[source], (
        "the cycle must be cached per source string"
    )

    first, second = next(rendered), next(rendered)
    assert isinstance(first, bytes) and len(first) > 0
    assert isinstance(second, bytes) and len(second) > 0
    # red frame vs blue frame: distinctness proves a multi-frame decode
    assert first != second


def test_animated_data_uri_is_shared_between_buttons(dummy_deck):
    """Same source string on two buttons → one decode, one shared cycle."""
    import base64
    from pathlib import Path

    gif_bytes = (
        Path(__file__).resolve().parents[1] / "e2e" / "assets" / "red-blue.gif"
    ).read_bytes()
    source = f"data:image/gif;base64,{base64.b64encode(gif_bytes).decode('ascii')}"

    from_button_1 = runner.render_key_image(dummy_deck, source)
    from_button_2 = runner.render_key_image(dummy_deck, source)
    assert from_button_1 is from_button_2
    assert runner.persistent_images[source] is from_button_1


# ---------------------------------------------------------------
# Round 3A (assign→render loop): a config assigned to a device via
# PUT /device/{id}/config/{config_id} is the exact dict the runner's
# button state machine consumes, and update_key_image writes real
# native key-image bytes onto the deck.
# ---------------------------------------------------------------
def test_assigned_config_drives_button_render(client, dummy_deck, monkeypatch):
    from pathlib import Path

    # A tiny local-file style image source (no data URI) — the same shape
    # the UI stores for path-based images.
    idle_image = str(
        Path(__file__).resolve().parents[1] / "e2e" / "assets" / "red-blue.gif"
    )

    # 1. Create a config over the API: two labeled buttons, button 0 a
    #    two-state toggle whose states carry no image override.
    created = client.post(
        "/config",
        json={
            "name": "Assigned Render",
            "deviceType": "stream-deck-xl",
            "buttons": [
                {
                    "index": 0,
                    "idle": {"text": "A", "image": idle_image},
                    "isToggle": True,
                    "toggleStates": [
                        {"name": "S0"},
                        {"name": "S1", "text": "B-alt"},
                    ],
                },
                {"index": 1, "idle": {"text": "B"}},
            ],
        },
    ).json()

    # 2. Assign it to the first device and read it back through the
    #    runner-facing endpoint.
    device = client.get("/devices").json()[0]
    assert (
        client.put(f"/device/{device['id']}/config/{created['id']}").status_code == 200
    )
    payload = client.get(f"/device/{device['id']}/config").json()
    assert payload["config"]["id"] == created["id"]
    assert payload["device"]["currentConfigId"] == created["id"]
    assigned = payload["config"]
    assert {b["index"]: b["idle"]["text"] for b in assigned["buttons"]} == {
        0: "A",
        1: "B",
    }

    # 3. Drive the runner with the assigned config exactly as run_deck would.
    runner.config = assigned
    runner.buttons.clear()

    idle = runner.get_button_config(0, False)
    assert idle["text"] == "A"  # state 0 has no overrides → inherits idle text
    assert idle["image"] == idle_image  # ...and idle image

    non_toggle = runner.get_button_config(1, False)
    assert non_toggle["text"] == "B"

    pressed = runner.get_button_config(0, True)
    assert runner.buttons[0]["state"] == 1  # press advanced the toggle
    assert pressed["text"] == "B-alt"  # state 1's text override wins...
    assert pressed["image"] == idle_image  # ...but the idle image is inherited

    # 4. One button renders to real native key-image bytes on the deck.
    written: list[bytes] = []
    real_set_key_image = dummy_deck.set_key_image

    def spy_set_key_image(key, image):
        written.append(image)
        real_set_key_image(key, image)

    monkeypatch.setattr(dummy_deck, "set_key_image", spy_set_key_image)
    runner.update_key_image(dummy_deck, 0, state=False)

    assert written, "update_key_image must write to the deck"
    assert isinstance(written[0], bytes)
    assert len(written[0]) > 0


def test_toggle_state_advances_on_press():
    """The 3-state toggle cycle: idle reads state 0, each press advances
    S0→S1→S2 and wraps back to S0; a state with only a text override still
    inherits the idle image (merge semantics)."""
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    idle_image = (
        "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    )

    runner.config = {
        "name": "Cycle",
        "buttons": [
            {
                "index": 0,
                "idle": {"text": "idle", "image": idle_image},
                "isToggle": True,
                "toggleStates": [
                    {"name": "S0", "text": "S0"},
                    {"name": "S1", "text": "S1"},  # text override only, no image
                    {"name": "S2", "text": "S2"},
                ],
            }
        ],
    }
    runner.buttons.clear()

    idle = runner.get_button_config(0, False)
    assert idle["text"] == "S0"
    assert idle["image"] == idle_image

    seen: list[tuple[int, str, str]] = []
    for _ in range(3):
        cfg = runner.get_button_config(0, True)
        seen.append(
            (runner.buttons[0]["state"], cfg["text"], cfg["image"])
        )

    assert [state for state, _, _ in seen] == [1, 2, 0]  # advances, then wraps
    assert [text for _, text, _ in seen] == ["S1", "S2", "S0"]
    # every state — including text-only overrides — keeps the idle image
    assert all(image == idle_image for _, _, image in seen)


# ---------------------------------------------------------------
# Round 3B (P13) — animation pause on a frame. Pause state is keyed
# by the image SOURCE string (consistent with P10's shared cycle):
# pausing pauses that GIF for every button showing it. The bare
# strings "pause" / "play" / "toggle-animation" and the dict forms
# {"type": ...} are equivalent; the animate tick must neither pull
# nor write a paused source, and resume continues from the held
# position (never resets to frame 0).
# ---------------------------------------------------------------
def _install_three_frame_source():
    """Direct-construct a 3-frame shared source the way render_key_image
    leaves it: one cycle in persistent_images, button 0 configured to show
    it (idle image "src")."""
    import itertools

    runner.persistent_images["src"] = itertools.cycle([b"f0", b"f1", b"f2"])
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"image": "src"}}],
    }


def test_pause_action_holds_frame(dummy_deck, monkeypatch):
    _install_three_frame_source()
    # "src" is a synthetic source string (no real file), so mock the render
    # pipeline: hand back the REAL shared cycle for "src" (so first paint
    # consumes f0 exactly like a real multi-frame decode would) and a
    # static sentinel for any other source (the blank press-repaint must
    # never touch the cycle). The cycle + pause machinery stays real.
    monkeypatch.setattr(
        runner,
        "render_key_image",
        lambda deck, source, *a, **k: runner.persistent_images["src"]
        if source == "src"
        else b"static-frame",
    )
    runner.update_key_image(dummy_deck, 0, False)  # register + first paint
    runner.buttons[0] = {"state": 0, "action": "pause"}

    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is True

    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda k, f: writes.append((k, f))
    )

    runner.animate_tick(dummy_deck)
    assert writes == [], "a paused source must be neither pulled nor written"

    # The cycle must be untouched by paused ticks. After the first paint the
    # cycle sits at f1; two paused ticks must consume nothing, so the next
    # two pulls still yield f1 then f2 (a buggy tick would push them to f2/f0).
    cyc = runner.persistent_images["src"]
    assert next(cyc) == b"f1"
    runner.animate_tick(dummy_deck)
    assert next(cyc) == b"f2"


def test_resume_continues_from_held_position(dummy_deck, monkeypatch):
    _install_three_frame_source()
    # "src" is a synthetic source string (no real file), so mock the render
    # pipeline: hand back the REAL shared cycle for "src" (so first paint
    # consumes f0 exactly like a real multi-frame decode would) and a
    # static sentinel for any other source (animation presses never
    # re-render the source). The cycle + pause machinery stays real.
    monkeypatch.setattr(
        runner,
        "render_key_image",
        lambda deck, source, *a, **k: runner.persistent_images["src"]
        if source == "src"
        else b"static-frame",
    )
    runner.update_key_image(dummy_deck, 0, False)  # register + first paint

    # One playing tick displays f1; the cycle now sits at f2.
    runner.animate_tick(dummy_deck)

    runner.buttons[0] = {"state": 0, "action": "pause"}
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is True

    runner.animate_tick(dummy_deck)  # paused tick: holds position

    runner.buttons[0]["action"] = "play"
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is False

    # Spy on writes only from here: the play press repaints nothing (see
    # test_animation_action_press_keeps_held_frame_visible) but
    # is not what this test is about. Only the resume tick's write is
    # asserted.
    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda k, f: writes.append((k, f))
    )

    runner.animate_tick(dummy_deck)
    assert writes == [(0, b"f2")], (
        "resume must continue from the held position (f2 next), not restart "
        "the cycle at its first frame"
    )


def test_toggle_animation_action_contract(dummy_deck):
    _install_three_frame_source()

    # Bare-string form flips the flag on each press.
    runner.buttons[0] = {"state": 0, "action": "toggle-animation"}
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is True
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is False

    # Dict forms are equivalent: toggle, pause, play.
    for dict_action, expected in (
        ({"type": "toggle-animation"}, True),
        ({"type": "pause"}, True),
        ({"type": "play"}, False),
    ):
        runner.buttons[0]["action"] = dict_action
        runner.key_change_callback(dummy_deck, 0, True)
        assert runner.paused_images["src"] is expected, dict_action


def test_start_paused_config(dummy_deck, monkeypatch):
    """Button-level animation {paused, frameIndex}: registration pauses the
    source and advances the shared cycle frameIndex times BEFORE the first
    paint — frameIndex=2 paints frame index 2 (the 3rd frame). Paused
    sources are then held: animate ticks neither pull nor write."""
    import base64
    import io
    from pathlib import Path

    from PIL import Image, ImageSequence

    gif_bytes = (
        Path(__file__).resolve().parents[1] / "e2e" / "assets" / "tri-color.gif"
    ).read_bytes()
    source = f"data:image/gif;base64,{base64.b64encode(gif_bytes).decode('ascii')}"

    # Expected native frames, decoded exactly the way the runner decodes
    # the data URI (same bytes → same frames → byte-identical conversion).
    decoded = Image.open(io.BytesIO(gif_bytes))
    expected = [
        runner.convert_image(dummy_deck, frame)
        for frame in ImageSequence.Iterator(decoded)
    ]
    assert len(expected) == 3, "tri-color.gif must decode to 3 frames"

    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [
            {
                "index": 0,
                "idle": {"image": source},
                "animation": {"paused": True, "frameIndex": 2},
            },
        ],
    }

    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda k, f: writes.append((k, f))
    )

    runner.update_key_image(dummy_deck, 0, state=False)

    assert runner.persistent_image_buttons[0] == source
    assert runner.paused_images[source] is True
    assert writes, "first paint must happen at registration"
    assert writes[0][1] == expected[2], (
        "frameIndex=2 must advance the cycle twice before the first paint"
    )

    # Paused after registration: an animate tick must hold the frame.
    runner.animate_tick(dummy_deck)
    assert len(writes) == 1


# ---------------------------------------------------------------
# Round 4 (P14/P15) — command launch modes + switch-config action.
# ---------------------------------------------------------------

def test_config_switch_action_swaps_config_and_rerenders(dummy_deck, monkeypatch):
    """P15 dict form: {"type": "switch-config", "configId": "..."} — the
    runner fetches that config from the API, swaps the module `config`,
    and re-renders every key (state False)."""
    runner.config = {
        "name": "Old Config",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "old"}}],
    }
    new_config = {
        "name": "New Config",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "new"}}],
    }

    class FakeResponse:
        status_code = 200
        ok = True

        def json(self):
            return new_config

    monkeypatch.setattr(runner, "requests", type("R", (), {"get": staticmethod(lambda *a, **k: FakeResponse())}))

    calls: list[tuple[int, bool]] = []

    def spy_update_key_image(deck, key, state):
        calls.append((key, state))

    monkeypatch.setattr(runner, "update_key_image", spy_update_key_image)

    runner.get_button_config(0, state=False)
    runner.buttons[0]["action"] = {"type": "switch-config", "configId": "cfg-2"}
    runner.key_change_callback(dummy_deck, 0, True)

    assert runner.config["name"] == "New Config", (
        "switch-config must swap the active config"
    )
    # Re-render: EVERY deck key at idle (state=False) — the deck is a 32-key
    # XL, and a swap repaints the whole surface, not just pressed buttons.
    assert calls[0] == (0, False)
    assert all(state is False for _, state in calls)
    assert len(calls) == dummy_deck.key_count()


def test_config_switch_bare_string_form(dummy_deck, monkeypatch):
    """P15 bare-string form: "switch-config:<config_id>" is equivalent to
    the dict form."""
    runner.config = {
        "name": "Old Config",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "old"}}],
    }
    new_config = {
        "name": "Switched",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "switched"}}],
    }

    class FakeResponse:
        status_code = 200

        def json(self):
            return new_config

    monkeypatch.setattr(runner.requests, "get", lambda *a, **k: FakeResponse())

    runner.get_button_config(0, state=False)
    runner.buttons[0]["action"] = "switch-config:cfg-42"
    runner.key_change_callback(dummy_deck, 0, True)

    assert runner.config["name"] == "Switched"


def test_config_switch_unknown_config_keeps_current(dummy_deck, monkeypatch):
    """Crash-safety: a 404 (or any non-200) must keep the CURRENT config
    and must not raise — a bad id on a button can never take the runner
    down."""
    original = {
        "name": "Keep Me",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "keep"}}],
    }
    runner.config = original
    calls: list[tuple[int, bool]] = []

    class FakeResponse:
        status_code = 404

        def json(self):
            return {"detail": "Configuration not found"}

    monkeypatch.setattr(runner.requests, "get", lambda *a, **k: FakeResponse())

    def spy_update_key_image(deck, key, state):
        calls.append((key, state))

    monkeypatch.setattr(runner, "update_key_image", spy_update_key_image)

    runner.get_button_config(0, state=False)
    runner.buttons[0]["action"] = {"type": "switch-config", "configId": "ghost"}
    runner.key_change_callback(dummy_deck, 0, True)  # must not raise

    assert runner.config is original
    # Design decision (documented): a FAILED switch falls through to normal
    # press handling, so the pressed button still repaints (its own key only
    # — no full-deck re-render, since the config didn't change).
    assert calls == [(0, True)]


def test_config_switch_api_down_keeps_current_config(dummy_deck, monkeypatch):
    """Crash-safety: the API being unreachable (requests raising) must log
    and keep the current config, never propagate."""
    original = {
        "name": "Keep Me",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "keep"}}],
    }
    runner.config = original

    def boom(*a, **k):
        raise ConnectionError("API down")

    monkeypatch.setattr(runner.requests, "get", boom)

    runner.get_button_config(0, state=False)
    runner.buttons[0]["action"] = {"type": "switch-config", "configId": "cfg-9"}
    runner.key_change_callback(dummy_deck, 0, True)  # must not raise

    assert runner.config is original


def test_fetch_config_by_id_uses_config_endpoint(monkeypatch):
    """fetch_config_by_id mirrors fetch_assigned_config: GET /config/{id}
    and returns the parsed body (the config dict itself)."""
    seen: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"name": "Fetched", "buttons": []}

    def fake_get(url, timeout=None):
        seen["url"] = url
        return FakeResponse()

    monkeypatch.setattr(runner.requests, "get", fake_get)
    result = runner.fetch_config_by_id("http://localhost:8000", "abc123")
    assert seen["url"] == "http://localhost:8000/config/abc123"
    assert result == {"name": "Fetched", "buttons": []}


# ---------------------------------------------------------------
# Round 4 hardening sweep (crash-safety): no exception raised inside
# the key callback may kill the runner — the StreamDeck library stops
# delivering callbacks from a raising handler, which would silently
# brick every button press until restart.
# ---------------------------------------------------------------
def test_key_callback_survives_dispatch_failure(dummy_deck, monkeypatch):
    """A dispatch_action that raises (API explodes mid-press) must not
    propagate out of key_change_callback."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [
            {"index": 0, "action": {"type": "command", "executable": "x"}}
        ],
    }

    def explode(deck, key, btn_action):
        raise RuntimeError("simulated dispatch explosion")

    monkeypatch.setattr(runner, "post_agent_action", explode)
    runner.get_button_config(0, state=False)

    # Must NOT raise, even though post_agent_action explodes before the
    # runner's own try/except around it.
    runner.key_change_callback(dummy_deck, 0, True)


def test_key_callback_survives_repaint_failure(dummy_deck, monkeypatch):
    """The repaint after the action path raising must not kill the
    callback either (update_key_image hitting a transport error, say)."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "x"}}],
    }

    def explode(deck, key, state):
        raise RuntimeError("simulated repaint explosion")

    monkeypatch.setattr(runner, "update_key_image", explode)
    runner.get_button_config(0, state=False)

    runner.key_change_callback(dummy_deck, 0, True)  # must not raise


def test_get_button_config_with_corrupt_config_returns_blank():
    """A corrupt config (buttons = None) must yield the blank-key dict, not
    a TypeError — configs arrive from the API/DB and must be defended."""
    runner.config = {"name": "Corrupt", "buttons": None}
    runner.buttons.clear()

    cfg = runner.get_button_config(0, state=False)
    assert cfg == {"image": None, "text": None}


def test_get_button_config_with_config_none_returns_blank():
    runner.config = None
    runner.buttons.clear()

    cfg = runner.get_button_config(3, state=False)
    assert cfg == {"image": None, "text": None}


def test_detached_result_status_is_detached_via_roundtrip_wire():
    """P14 wire contract: AgentAction.action is a schema-less JSON column —
    the mode field must pass through build_agent_action + a simulated
    JSON round-trip verbatim, exactly like timeout/env (P8)."""
    import json as _json

    action = {
        "type": "command",
        "executable": "/usr/bin/open",
        "arguments": "-a Safari",
        "mode": "detached",
    }
    wrapped = agent.build_agent_action(action, device_id="DUM", button_index=1)
    assert wrapped["action"]["mode"] == "detached"
    # JSON column round-trip: mode survives verbatim.
    roundtripped = _json.loads(_json.dumps(wrapped["action"]))
    assert roundtripped["mode"] == "detached"


def test_pause_is_shared_across_buttons(dummy_deck, monkeypatch):
    """P13 shared-pause semantics: pause is keyed by the image SOURCE, so a
    pause action on ONE button holds the frame for EVERY button showing
    that source — a pressed pause on key 0 must leave key 1's animation
    held too, and the shared cycle must not advance for either."""
    _install_three_frame_source()
    runner.config["buttons"].append({"index": 1, "idle": {"image": "src"}})
    # Same documented workaround as the tests above: "src" is synthetic, so
    # render is mocked to hand back the REAL shared cycle for "src" (first
    # paints consume the cycle like a real decode would) and a static
    # sentinel for any other source (the blank press-repaint must never
    # touch the cycle).
    monkeypatch.setattr(
        runner,
        "render_key_image",
        lambda deck, source, *a, **k: runner.persistent_images["src"]
        if source == "src"
        else b"static-frame",
    )
    runner.update_key_image(dummy_deck, 0, False)
    runner.update_key_image(dummy_deck, 1, False)
    assert runner.persistent_image_buttons[0] == "src"
    assert runner.persistent_image_buttons[1] == "src"

    # Pause via key 0's action only — key 1 is never pressed.
    runner.buttons[0] = {"state": 0, "action": "pause"}
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is True

    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda k, f: writes.append((k, f))
    )
    runner.animate_tick(dummy_deck)
    assert writes == [], (
        "a shared pause must hold EVERY button showing the source: neither "
        "key 0 nor key 1 may be written while the source is paused"
    )

    # The cycle did not advance during the paused tick. Both first paints
    # consumed frames (key 0 shows f0, key 1 shows f1 — one shared cycle,
    # per P10), so the cycle sits at f2; a buggy tick that pulls-while-
    # paused would have pushed it to f0.
    assert next(runner.persistent_images["src"]) == b"f2"


def test_animation_action_press_keeps_held_frame_visible(dummy_deck, monkeypatch):
    """P13 press-repaint regression: pressing an animation control must not
    blank the button. The pre-fix code repainted the key with BLANK_IMAGE
    (these actions configure no pressed image), blanking the held frame the
    feature exists to show — so the press must write NOTHING and leave the
    frame already on the key (and the shared cycle) untouched."""
    _install_three_frame_source()
    monkeypatch.setattr(
        runner,
        "render_key_image",
        lambda deck, source, *a, **k: runner.persistent_images["src"]
        if source == "src"
        else b"static-frame",
    )
    runner.update_key_image(dummy_deck, 0, False)  # register + first paint (f0)

    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda k, f: writes.append((k, f))
    )

    runner.buttons[0] = {"state": 0, "action": "pause"}
    runner.key_change_callback(dummy_deck, 0, True)
    assert runner.paused_images["src"] is True

    assert writes == [], (
        "the pause press must not repaint the key at all: no BLANK_IMAGE "
        "may land on the held frame"
    )
    # ...and the press must not consume the shared cycle (still at f1).
    assert next(runner.persistent_images["src"]) == b"f1"


# ---------------------------------------------------------------
# P18 — sequence actions flow through the SAME agent-execution path as
# command dicts: pressing a button whose action is
# {"type": "sequence", "steps": [...]} must enqueue the payload verbatim
# via post_agent_action (the JSON column preserves nested dicts — the
# round-2 proof). Monkeypatched here so no API server is needed.
# ---------------------------------------------------------------
def test_sequence_action_reaches_agent_queue(dummy_deck, monkeypatch):
    """Pressing a button with a sequence action must post the dict verbatim
    to the agent-actions queue (same path as commands)."""
    captured: list[dict] = []
    monkeypatch.setattr(runner, "post_agent_action", lambda a: captured.append(a) or {})

    action = {
        "type": "sequence",
        "steps": [
            {"type": "command", "executable": "/bin/echo", "arguments": "hi"},
            {"type": "command", "executable": "/usr/bin/true"},
        ],
    }
    runner.config = {
        "name": "Seq Dispatch",
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "action": action, "idle": {"text": "seq"}}],
    }
    runner.get_button_config(0, state=False)
    runner.key_change_callback(dummy_deck, 0, True)

    assert captured, "a sequence press must enqueue the action"
    assert captured[0]["action"] == action, (
        "the sequence payload must pass through verbatim"
    )
    assert captured[0]["buttonIndex"] == 0
    assert captured[0]["deviceId"] == dummy_deck.get_serial_number()
