# test_runner.py — the device runner driven against a dummy deck.
#
# This is the end-to-end heart of the port: config JSON in, real library
# rendering out, key callbacks dispatched — no hardware required.

from __future__ import annotations

import argparse
import json
import threading
import time

import pytest

from streamdeck import runner


CONFIG = {
    "device_type": "stream-deck-xl",
    "buttons": [
        {
            "index": 0,
            "idle": {"text": "hello"},
            "action": {"type": "command", "executable": "true"},
        },
        {"index": 1, "toggleStates": [{"text": "off"}, {"text": "on"}]},
    ],
}


def _exit_key(deck):
    """Exit button: patch in a config entry for the deck's last key and use it."""
    last = deck.key_count() - 1
    runner.config["buttons"].append(
        {"index": last, "action": "exit", "idle": {"text": "quit"}}
    )
    return last


@pytest.fixture(autouse=True)
def loaded_config():
    runner.config = json.loads(json.dumps(CONFIG))
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.closed_event.clear()
    yield
    runner.closed_event.clear()


def test_blank_button_gets_placeholder_image(dummy_deck):
    cfg = runner.get_button_config(5, state=False)
    assert cfg == {"image": None, "text": None}

    runner.update_key_image(dummy_deck, 5, state=False)  # placeholder image path


def test_idle_and_pressed_states(dummy_deck):
    idle = runner.get_button_config(0, state=False)
    pressed = runner.get_button_config(0, state=True)
    assert idle["text"] == "hello"
    assert pressed == {} or "text" not in pressed

    runner.update_key_image(dummy_deck, 0, state=True)

def test_toggle_state_cycles(dummy_deck):
    first = runner.get_button_config(1, state=True)  # arms the toggle
    assert first["text"] == "off"
    second = runner.get_button_config(1, state=True)  # advances to "on"
    assert second["text"] == "on"
    third = runner.get_button_config(1, state=True)  # wraps to "off"
    assert third["text"] == "off"


def test_render_key_image_static(dummy_deck):
    native = runner.render_key_image(dummy_deck, runner.BLANK_IMAGE, "label")
    assert isinstance(native, bytes)
    assert len(native) > 0


def test_exit_action_closes_deck(dummy_deck):
    # The exit button is the last key; it maps to action "exit"
    exit_key = _exit_key(dummy_deck)
    # Prime the button state as the callback does
    runner.get_button_config(exit_key, state=False)
    runner.key_change_callback(dummy_deck, exit_key, True)
    assert runner.closed_event.is_set()
    assert not dummy_deck.is_open()


def test_exit_sets_closed_event_before_closing_deck(dummy_deck, monkeypatch):
    """
    Regression for polyrepo fix 1365341: the exit callback must signal
    closed_event BEFORE deck.reset()/deck.close(), so the animate thread
    stops polling before the transport goes away. Closing first leaves a
    race window where the animate thread can attempt writes on a closed
    deck (the original TransportError bug).
    """
    exit_key = _exit_key(dummy_deck)
    runner.get_button_config(exit_key, state=False)  # prime buttons dict

    order = []
    real_reset = dummy_deck.reset
    real_close = dummy_deck.close

    def spy_reset():
        order.append(("reset", runner.closed_event.is_set()))
        real_reset()

    def spy_close():
        order.append(("close", runner.closed_event.is_set()))
        real_close()

    monkeypatch.setattr(dummy_deck, "reset", spy_reset)
    monkeypatch.setattr(dummy_deck, "close", spy_close)

    runner.key_change_callback(dummy_deck, exit_key, True)

    assert order == [("reset", True), ("close", True)]
    assert not dummy_deck.is_open()


def test_dispatch_action_sends_to_queue(dummy_deck, monkeypatch):
    captured = {}

    def fake_enqueue(action):
        captured.update(action)
        return {"id": "queued"}

    monkeypatch.setattr(runner, "post_agent_action", fake_enqueue)
    # Key 0 has both idle text and a command action in the fixture config
    runner.get_button_config(0, state=False)
    runner.key_change_callback(dummy_deck, 0, True)
    assert captured["action"]["executable"] == "true"
    assert captured["buttonIndex"] == 0
    assert captured["deviceId"] == dummy_deck.get_serial_number()


def test_animate_thread_runs_without_hardware(dummy_deck):
    import threading

    runner.update_key_image(dummy_deck, 0, False)
    # A short-lived animate loop must render frames through the dummy
    # transport without raising.
    animate = threading.Thread(target=_short_animate, args=(dummy_deck,), daemon=True)
    animate.start()
    animate.join(timeout=2.0)
    assert not animate.is_alive()


def _make_animated_gif(path):
    from PIL import Image

    frames = [Image.new("RGB", (72, 72), color) for color in ("red", "blue")]
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=50,
        loop=0,
    )


def test_run_deck_honors_closed_event_while_deck_open(dummy_deck, monkeypatch, tmp_path):
    """
    Regression for polyrepo fix 1365341: both loops inside run_deck (the
    30fps animate thread and the main blocking loop) must stop on
    closed_event alone — no deck.close() required — and the animate thread
    must never issue a write against a closed deck.
    """
    # An animated image on button 0 keeps the animate thread writing every
    # frame, so the write-count assertions below are not vacuous.
    gif = tmp_path / "animated.gif"
    _make_animated_gif(str(gif))
    runner.config["buttons"][0]["idle"]["image"] = str(gif)

    # Skip the REST API lookup; run_deck falls back to the loaded config.
    monkeypatch.setattr(runner, "fetch_assigned_config", lambda api, device_id: None)

    violations = []
    writes = {"n": 0}
    real_set_key_image = dummy_deck.set_key_image

    def spy_set_key_image(key, image):
        writes["n"] += 1
        if not dummy_deck.is_open():
            violations.append(key)
        real_set_key_image(key, image)

    monkeypatch.setattr(dummy_deck, "set_key_image", spy_set_key_image)

    args = argparse.Namespace(
        config=None,
        brightness=30,
        list_devices=False,
        device_type=None,
        ignore_device_type_check=False,
        api="http://localhost:8000",
        device_id=None,
    )

    errors = []

    def target():
        try:
            runner.run_deck(dummy_deck, args)
        except BaseException as err:  # surfaced via assertions below
            errors.append(err)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    # Wait for the animate thread to render at least one frame.
    deadline = time.monotonic() + 5.0
    while writes["n"] == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert writes["n"] > 0, "animate thread never rendered a frame"
    assert not errors, errors

    # Signal shutdown WITHOUT closing the deck: both loops must exit.
    runner.closed_event.set()
    thread.join(timeout=3.0)
    assert not thread.is_alive(), "run_deck ignored closed_event"
    assert dummy_deck.is_open(), "deck must stay open until close() is called"
    assert not errors, errors

    # Let any in-flight frame land, then confirm rendering has stopped even
    # though the deck is still open, and that no write hit a closed deck.
    time.sleep(0.15)
    frozen = writes["n"]
    time.sleep(0.15)
    assert writes["n"] == frozen, "animate thread kept rendering after closed_event"
    assert violations == []
    assert not errors, errors


def _short_animate(deck):
    from fractions import Fraction
    import itertools

    frame_time = Fraction(1, 30)
    next_frame = Fraction(runner.time.monotonic())
    deadline = time.time() + 0.2
    while time.time() < deadline and deck.is_open():
        try:
            with deck:
                for key, image in runner.persistent_images.items():
                    next(image)
        except Exception:  # TransportError
            break
        next_frame += frame_time
        sleep_for = float(next_frame) - runner.time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)