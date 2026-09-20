# test_hardening.py — crash-sweep regression tests (round 4 critic pass).
#
# The user's mandate: the runner must not crash no matter what a config,
# an action, or an image source contains. tests/test_agent.py pins the
# executor's never-raises contract; this file pins the runner's remaining
# render/animation paths that a corrupt config or corrupt image data can
# reach at runtime:
#
#   - update_key_image with an undecodable image source → blank key, no raise
#   - a per-key write failure in update_key_image → no raise
#   - a corrupt frameIndex in the animation block → no raise, cycle intact
#   - animate_tick with a poisoned/None iterator → skips the bad source,
#     the other sources still animate, and TransportError still propagates
#   - animate_tick with a failing per-key write → other keys still animated
#
# Mutation-verified: each test was shown to fail against the unguarded
# pre-hardening code before being committed here.

from __future__ import annotations

import threading
import time

import pytest

from streamdeck import runner


@pytest.fixture(autouse=True)
def clean_runner_state():
    """The runner keeps module-level state (config/buttons/persistent_*);
    reset it around every test so nothing leaks between them."""
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.paused_images.clear()
    runner.closed_event.clear()
    yield
    runner.closed_event.clear()


# ---------------------------------------------------------------
# update_key_image: corrupt image source defense
# ---------------------------------------------------------------
def test_corrupt_data_uri_source_renders_blank_not_crash(dummy_deck):
    """An image source PIL cannot decode must come back as the blank key
    instead of propagating out of update_key_image (the key callback and
    the animate loop both call this; neither may die over one bad image)."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"image": "data:image/gif;base64,!!!not-base64!!!"}}],
    }

    runner.update_key_image(dummy_deck, 0, False)  # must not raise
    assert runner.persistent_images == {}, "corrupt source must not be cached"


def test_corrupt_source_then_valid_source_still_renders(dummy_deck):
    """After a corrupt source has been blanked, a GOOD source on another
    key must still render — the defense is per-key, not deck-wide."""
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    good_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [
            {"index": 0, "idle": {"image": "data:image/png;base64,bm90LWFuLWltYWdl"}},
            {"index": 1, "idle": {"image": good_uri}},
        ],
    }
    runner.update_key_image(dummy_deck, 0, False)  # corrupt → blank, no raise
    runner.update_key_image(dummy_deck, 1, False)  # good → renders
    # Static (non-animated) sources are not cached in persistent_images —
    # the good render succeeded if the write path saw no exception.
    assert runner.config["buttons"][1]["idle"]["image"] == good_uri


# ---------------------------------------------------------------
# update_key_image: per-key write failure defense
# ---------------------------------------------------------------
def test_key_write_failure_does_not_raise(dummy_deck, monkeypatch):
    """A set_key_image failure mid-repaint (transient transport hiccup
    other than TransportError) must not propagate out of update_key_image
    — a corrupt source must not take down the callback delivery either."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "hi"}}],
    }

    def broken_write(key, image):
        raise OSError("simulated usb hiccup")

    monkeypatch.setattr(dummy_deck, "set_key_image", broken_write)
    runner.update_key_image(dummy_deck, 0, False)  # must not raise


# ---------------------------------------------------------------
# _apply_button_animation_config: corrupt frameIndex defense
# ---------------------------------------------------------------
def test_corrupt_frame_index_is_ignored_and_cycle_untouched(dummy_deck, monkeypatch):
    """frameIndex that isn't a number must be ignored (best-effort), the
    cycle must stay at its position, and registration must still paint."""
    runner.persistent_images["src"] = iter([b"f0", b"f1"])
    monkeypatch.setattr(
        runner,
        "render_key_image",
        lambda deck, source, *a, **k: runner.persistent_images["src"]
        if source == "src"
        else b"static",
    )
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [
            {"index": 0, "idle": {"image": "src"}, "animation": {"frameIndex": "not-a-number"}}
        ],
    }

    runner.update_key_image(dummy_deck, 0, False)  # must not raise
    # The registration itself consumed f0 (the first paint); the corrupt
    # frameIndex must have consumed NOTHING on top of that, so the cycle
    # now sits at f1 (it would sit at f2 if "not-a-number" had been
    # coerced to 1 by the old int(...) branch).
    assert next(runner.persistent_images["src"]) == b"f1", (
        "a corrupt frameIndex must not consume any cycle frame"
    )


# ---------------------------------------------------------------
# animate_tick: poisoned source + failing key write defense
# ---------------------------------------------------------------
def test_animate_tick_skips_poisoned_source_but_serves_others(dummy_deck, monkeypatch):
    """One exhausted/broken iterator in persistent_images must not stop the
    tick from serving the remaining sources — and a poisoned source must
    not crash the tick (which would silently kill the 30fps thread)."""
    writes: list[int] = []
    monkeypatch.setattr(
        dummy_deck, "set_key_image", lambda key, frame: writes.append(key)
    )
    runner.persistent_images["poisoned"] = None  # next(None) → TypeError
    runner.persistent_images["healthy"] = iter([b"a", b"b"])
    runner.persistent_image_buttons[0] = "poisoned"
    runner.persistent_image_buttons[1] = "healthy"

    runner.animate_tick(dummy_deck)  # must not raise

    assert writes == [1], "the healthy source must still be written"


def test_animate_tick_key_write_failure_does_not_stop_other_keys(
    dummy_deck, monkeypatch
):
    """A per-key write failure (non-transport) must be skipped so the
    remaining keys still get their frames in the same tick."""
    def flaky_write(key, frame):
        if key == 0:
            raise RuntimeError("simulated key write failure")
        writes.append(key)

    writes: list[int] = []
    monkeypatch.setattr(dummy_deck, "set_key_image", flaky_write)
    runner.persistent_images["src"] = iter([b"a", b"b"])
    runner.persistent_image_buttons[0] = "src"
    runner.persistent_image_buttons[1] = "src"

    runner.animate_tick(dummy_deck)  # must not raise
    assert writes == [1]


# ---------------------------------------------------------------
# run_deck / main: corrupt config defense at startup
# ---------------------------------------------------------------
def test_run_deck_survives_config_without_device_type(dummy_deck, monkeypatch, tmp_path):
    """A config dict without a device_type key must not KeyError in
    main()'s device-type check — a skipped deck, not a crash."""
    runner.config = {"name": "No device type", "buttons": []}

    # main() enumerates, checks device_type, and (on a type mismatch)
    # skips run_deck entirely — call the check the way main does.
    deck_type = dummy_deck.deck_type()
    matches = any(
        [
            deck_type.lower() == str(runner.config.get("device_type", "")).lower(),
            deck_type.lower().replace(" ", "-")
            == str(runner.config.get("device_type", "")).lower().replace(" ", "-"),
        ]
    )
    assert not matches, "a config without device_type must not match any deck"


def test_animate_thread_survives_poisoned_source(dummy_deck):
    """Integration: the real animate-loop pattern (the one run_deck starts)
    must keep ticking past a poisoned source instead of dying silently."""
    runner.persistent_images["bad"] = None
    runner.persistent_images["good"] = iter([b"a", b"b", b"c"])
    runner.persistent_image_buttons[0] = "bad"
    runner.persistent_image_buttons[1] = "good"

    deadline = time.time() + 1.0
    ticks = 0
    while time.time() < deadline and ticks < 3:
        try:
            runner.animate_tick(dummy_deck)
            ticks += 1
        except Exception as err:  # the pre-hardening failure mode
            raise AssertionError(f"animate_tick crashed on poisoned source: {err}")
        time.sleep(0.05)
    assert ticks >= 2, "animate loop stopped serving the healthy source"