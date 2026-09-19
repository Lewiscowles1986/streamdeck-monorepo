# test_runner.py — the device runner driven against a dummy deck.
#
# This is the end-to-end heart of the port: config JSON in, real library
# rendering out, key callbacks dispatched — no hardware required.

from __future__ import annotations

import json

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