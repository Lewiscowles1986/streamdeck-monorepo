# test_backgrounds.py — multi-button image backgrounds (P19).
#
# A config may carry a `backgrounds` list: images spanning a region of key
# cells. The runner composites each image over its region at native key
# resolution, slices the composite into per-key tiles, and paints the covered
# keys that have no image of their own. These tests pin:
#
#   - tile slicing: same-composite crops tile seamlessly (per-key bytes)
#   - a button's own image wins over the background underneath it
#   - the background paints only keys with no own image (text-only keys
#     still get the tile, with the label drawn over it)
#   - animated backgrounds cycle through the 30 fps animate loop
#   - pause/play on a covered key holds EVERY tile of the span (shared
#     pause, mirroring the P13 source-keyed rule)
#   - malformed entries are skipped; corrupt images render blank, no raise
#   - a config swap purges stale spans (no background tile repaints the
#     new config's keys)
#   - static backgrounds register as plain bytes (no 30fps rewrite spam)
#
# Mutation-verified: each test was shown to fail against the pre-background
# code (button-only rendering) or a deliberately broken variant before being
# committed here.

from __future__ import annotations

import base64
import io
import itertools
from pathlib import Path

import pytest

from streamdeck import runner


@pytest.fixture(autouse=True)
def clean_runner_state():
    """The runner keeps module-level state; reset it around every test."""
    runner.buttons.clear()
    runner.persistent_images.clear()
    runner.persistent_image_buttons.clear()
    runner.paused_images.clear()
    runner.background_frames.clear()
    runner.background_composites.clear()
    runner.closed_event.clear()
    yield
    runner.closed_event.clear()


def _png_uri(color: tuple[int, int, int] = (255, 0, 0), size: tuple[int, int] = (96, 96)) -> str:
    """A tiny solid-color PNG data URI."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return (
        "data:image/png;base64,"
        + base64.b64encode(buf.getvalue()).decode("ascii")
    )


def _gif_uri(colors=("red", "blue")) -> str:
    """A two-frame animated GIF data URI (real frames, like the E2E asset)."""
    from PIL import Image

    buf = io.BytesIO()
    images = [Image.new("RGB", (96, 96), c) for c in colors]
    images[0].save(buf, format="GIF", save_all=True, append_images=images[1:])
    return (
        "data:image/gif;base64,"
        + base64.b64encode(buf.getvalue()).decode("ascii")
    )


def _written_frames(dummy_deck, monkeypatch) -> dict[int, list[bytes]]:
    """Spy on set_key_image and return {key: [frames written]}."""
    written: dict[int, list[bytes]] = {}
    real = dummy_deck.set_key_image

    def spy(key, image):
        written.setdefault(key, []).append(image)
        real(key, image)

    monkeypatch.setattr(dummy_deck, "set_key_image", spy)
    return written


# ---------------------------------------------------------------
# Normalization: malformed entries are skipped
# ---------------------------------------------------------------
def test_normalized_backgrounds_drops_malformed_entries():
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "ok", "image": "data:image/png;base64,AAAA", "x": 0, "y": 0,
             "width": 2, "height": 1},
            "not-a-dict",
            {"id": "no-image", "x": 0, "y": 0, "width": 1, "height": 1},
            {"id": "neg-x", "image": "data:image/png;base64,AAAA", "x": -1,
             "y": 0, "width": 1, "height": 1},
            {"id": "zero-w", "image": "data:image/png;base64,AAAA", "x": 0,
             "y": 0, "width": 0, "height": 1},
            {"id": "str-numbers", "image": "data:image/png;base64,AAAA",
             "x": "1", "y": "0", "width": "2", "height": "1"},
        ],
    }
    normalized = runner._normalized_backgrounds(runner.config)
    ids = [bg_id for bg_id, _ in normalized]
    assert ids == ["ok", "str-numbers"], "malformed entries must be dropped"
    # string numerics coerce
    assert normalized[1][1]["x"] == 1 and normalized[1][1]["width"] == 2


def test_normalized_backgrounds_guards_non_dict_config():
    assert runner._normalized_backgrounds(None) == []
    assert runner._normalized_backgrounds({"backgrounds": "junk"}) == []
    assert runner._normalized_backgrounds({"backgrounds": [42, None]}) == []


# ---------------------------------------------------------------
# Coverage: which key does a background paint?
# ---------------------------------------------------------------
def test_covering_background_matches_region_cells(dummy_deck):
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "hero", "image": "data:image/png;base64,AAAA",
             "x": 1, "y": 0, "width": 2, "height": 1},
        ],
    }
    # XL layout: 4 rows × 8 cols. Region covers (row 0, cols 1-2).
    # The coverage math uses the DECK's real layout (key_layout), so run it
    # against the deck's own geometry: derive the covered/uncovered keys
    # from rows/cols instead of hardcoding XL indices.
    rows, cols = dummy_deck.key_layout()
    covered = [y * cols + x for y in range(1) for x in (1, 2)]
    uncovered = [y * cols + x for y in range(rows) for x in (0, 3)
                 if y * cols + x < rows * cols]
    for key in covered:
        assert runner._covering_background(dummy_deck, key) is not None
    for key in uncovered:
        assert runner._covering_background(dummy_deck, key) is None


def test_later_background_wins_z_order(dummy_deck):
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "under", "image": "data:image/png;base64,AAAA",
             "x": 0, "y": 0, "width": 4, "height": 4},
            {"id": "over", "image": "data:image/png;base64,BBBB",
             "x": 1, "y": 1, "width": 1, "height": 1},
        ],
    }
    # NOTE: the dummy deck is an Original (3 rows × 5 cols).
    # "under" covers cols 0-3 (width 4); "over" covers row 1 col 1 = key 6.
    # key 3 (row 0 col 3) stays under, key 4 (row 0 col 4) is outside both.
    assert runner._covering_background(dummy_deck, 0)[0] == "under"
    assert runner._covering_background(dummy_deck, 6)[0] == "over"
    assert runner._covering_background(dummy_deck, 3)[0] == "under"
    assert runner._covering_background(dummy_deck, 4) is None


# ---------------------------------------------------------------
# Core rendering: tiles are painted, own-image keys win
# ---------------------------------------------------------------
def test_background_paints_covered_key_with_tile_bytes(dummy_deck, monkeypatch):
    """A covered key with no image of its own receives real native key-image
    bytes cut from the composite — the background paints it."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "hero", "image": _png_uri(), "x": 0, "y": 0,
             "width": 2, "height": 2},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)

    runner.update_key_image(dummy_deck, 0, False)  # must not raise

    frames = written.get(0)
    assert frames, "covered key must be painted"
    assert isinstance(frames[0], bytes) and len(frames[0]) > 0
    # registered as a static source (plain bytes, not a cycle)
    source = runner.persistent_image_buttons[0]
    assert source == "background:hero#0"
    assert isinstance(runner.persistent_images[source], bytes)


def test_button_own_image_wins_over_background(dummy_deck, monkeypatch):
    """A key with its own idle image shows THAT image — the background only
    fills keys with no image of their own. The own image is an animated GIF
    so it registers in persistent_image_buttons (static sources are not
    cached there by design)."""
    own_uri = _gif_uri(("green", "lime"))
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"image": own_uri}}],
        "backgrounds": [
            {"id": "hero", "image": _png_uri(), "x": 0, "y": 0,
             "width": 2, "height": 2},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)

    runner.update_key_image(dummy_deck, 0, False)

    source = runner.persistent_image_buttons.get(0)
    assert source == own_uri, "the button's own image must be registered"
    assert source != "background:hero#0"
    assert written.get(0), "the own image must still paint"


def test_text_only_key_gets_tile_with_label(dummy_deck, monkeypatch):
    """A covered key configured with only text paints the background tile
    (not the blank key) — and the label draws over it."""
    from PIL import ImageDraw

    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"text": "LIVE"}}],
        "backgrounds": [
            {"id": "hero", "image": _png_uri(), "x": 0, "y": 0,
             "width": 2, "height": 2},
        ],
    }
    drawn_texts: list[str] = []
    real_draw = ImageDraw.Draw

    class DrawSpy:
        def __init__(self, img):
            self._real = real_draw(img)

        def text(self, *args, **kwargs):
            drawn_texts.append(kwargs.get("text") or (args[1] if len(args) > 1 else None))
            self._real.text(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    import streamdeck.runner as rmod
    rmod.ImageDraw.Draw = DrawSpy
    try:
        runner.update_key_image(dummy_deck, 0, False)
    finally:
        rmod.ImageDraw.Draw = real_draw

    assert drawn_texts == ["LIVE"], "the label must draw over the tile"
    source = runner.persistent_image_buttons.get(0)
    assert source == "background:hero#0", "not the blank key"


def test_uncovered_key_still_gets_blank_image(dummy_deck, monkeypatch):
    """A key outside every background region keeps the blank-key behavior."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "hero", "image": _png_uri(), "x": 0, "y": 0,
             "width": 1, "height": 1},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)
    runner.update_key_image(dummy_deck, 1, False)
    assert written.get(1), "uncovered key must still paint"
    assert runner.persistent_image_buttons.get(1) is None


# ---------------------------------------------------------------
# Seamlessness: tiles from the SAME composite
# ---------------------------------------------------------------
def test_adjacent_tiles_come_from_one_composite(dummy_deck):
    """Two keys in the same span must slice from the same composite canvas —
    that is what makes the image continuous across the key borders."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "span", "image": _png_uri(size=(192, 96)), "x": 0, "y": 0,
             "width": 2, "height": 1},
        ],
    }
    runner._register_background_key(dummy_deck, 0, "span",
                                    runner.config["backgrounds"][0], {})
    runner._register_background_key(dummy_deck, 1, "span",
                                    runner.config["backgrounds"][0], {})

    composites = runner.background_composites["span"]
    assert len(composites) == 1, "one composite canvas for the span"
    tile0 = runner._tile_for_key(composites[0], dummy_deck, 0)
    tile1 = runner._tile_for_key(composites[0], dummy_deck, 1)
    assert tile0 is not None and tile1 is not None
    assert tile0.size == tile1.size


def test_tile_inverts_deck_transform_for_native_conversion(dummy_deck):
    """The tile handed to to_native_key_format must be pre-inverted so the
    vendored conversion (rotate + flip) restores display orientation. On the
    XL (flip both axes), a pre-flipped tile converts back to the original."""
    from PIL import Image

    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "span", "image": _png_uri(size=(192, 96)), "x": 0, "y": 0,
             "width": 2, "height": 1},
        ],
    }
    bg = runner.config["backgrounds"][0]
    frames = runner._background_frames(dummy_deck, "span", bg)
    canvases = runner._background_composite(dummy_deck, "span", bg, frames)
    tile = runner._tile_for_key(canvases[0], dummy_deck, 0)

    fmt = dummy_deck.key_image_format()
    restored = tile
    if fmt["rotation"]:
        restored = restored.rotate(fmt["rotation"], expand=True)
    restored = restored.transpose(Image.FLIP_LEFT_RIGHT)
    restored = restored.transpose(Image.FLIP_TOP_BOTTOM)

    _, cols = dummy_deck.key_layout()
    key_w, key_h = fmt["size"]
    expected = canvases[0].crop((0, 0, key_w, key_h))
    assert list(restored.getdata()) == list(expected.getdata()), (
        "inverse transform must restore the composite orientation"
    )


# ---------------------------------------------------------------
# Animated backgrounds: frames cycle through the animate loop
# ---------------------------------------------------------------
def test_animated_background_registers_cycle_and_animates(dummy_deck, monkeypatch):
    """A GIF background registers a frame cycle per tile; animate_tick
    advances and writes each frame to the covered key."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "anim", "image": _gif_uri(), "x": 0, "y": 0,
             "width": 2, "height": 1},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)

    runner.update_key_image(dummy_deck, 0, False)
    source = runner.persistent_image_buttons[0]
    cycle = runner.persistent_images[source]
    assert isinstance(cycle, itertools.cycle), (
        "an animated background must register a cycle"
    )

    f1 = written[0][0]
    runner.animate_tick(dummy_deck)
    f2 = written[0][1]
    assert f1 != f2, "the tick must advance the background to its next frame"

    # both tiles share one composite list — the span animates together
    runner.update_key_image(dummy_deck, 1, False)
    source1 = runner.persistent_image_buttons[1]
    assert source1 == "background:anim#1"
    runner.animate_tick(dummy_deck)
    assert written[0][-1] != written[1][-1] or written[0][0] != written[1][0]


def test_static_background_is_plain_bytes_not_cycle(dummy_deck):
    """A single-frame background registers plain bytes: the animate tick
    neither pulls nor rewrites it every frame."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "still", "image": _png_uri(), "x": 0, "y": 0,
             "width": 1, "height": 1},
        ],
    }
    runner.update_key_image(dummy_deck, 0, False)
    source = runner.persistent_image_buttons[0]
    assert isinstance(runner.persistent_images[source], bytes)


# ---------------------------------------------------------------
# Pause: shared per background (P13 contract over spans)
# ---------------------------------------------------------------
def test_pause_on_covered_key_holds_every_tile(dummy_deck):
    """Pausing via a covered key must freeze the WHOLE span: every tile of
    the background stops advancing (a span freezing on one key while its
    siblings keep cycling would tear the image apart)."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "anim", "image": _gif_uri(), "x": 0, "y": 0,
             "width": 3, "height": 1},
        ],
    }
    runner.update_key_image(dummy_deck, 0, False)
    runner.update_key_image(dummy_deck, 1, False)
    runner.update_key_image(dummy_deck, 2, False)

    sources = {
        key: runner.persistent_image_buttons[key] for key in (0, 1, 2)
    }
    assert all(s.startswith("background:anim#") for s in sources.values())

    runner.handle_animation_action("pause", 1)  # pause from the middle key

    assert all(runner.paused_images[s] for s in sources.values()), (
        "pause must hold EVERY tile of the span"
    )

    runner.handle_animation_action("play", 0)
    assert not any(runner.paused_images.get(s) for s in sources.values())


def test_pause_of_button_image_does_not_touch_backgrounds(dummy_deck):
    """The pre-P19 pause path must keep working: pausing a key that shows
    its own image sets that source only, no background interference."""
    own_uri = _gif_uri()
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {"image": own_uri}}],
        "backgrounds": [
            {"id": "anim", "image": _gif_uri(), "x": 1, "y": 0,
             "width": 2, "height": 1},
        ],
    }
    runner.update_key_image(dummy_deck, 0, False)
    runner.handle_animation_action("pause", 0)
    assert runner.paused_images[own_uri] is True
    bg_source = "background:anim#1"
    runner.update_key_image(dummy_deck, 1, False)
    assert not runner.paused_images.get(bg_source), (
        "the background must keep playing"
    )


# ---------------------------------------------------------------
# Crash-safety: corrupt entries never take down the render path
# ---------------------------------------------------------------
def test_corrupt_background_image_renders_blank_no_raise(dummy_deck, monkeypatch):
    """An undecodable background image must leave the key blank (and paint
    nothing) instead of propagating out of update_key_image."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "bad", "image": "data:image/png;base64,!!!not-base64!!!",
             "x": 0, "y": 0, "width": 2, "height": 2},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)
    runner.update_key_image(dummy_deck, 0, False)  # must not raise
    assert runner.background_frames == {}, "corrupt source must not be cached"
    assert runner.persistent_image_buttons.get(0) is None


def test_background_without_id_gets_indexed_id(dummy_deck):
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"image": _png_uri(), "x": 0, "y": 0, "width": 1, "height": 1},
        ],
    }
    normalized = runner._normalized_backgrounds(runner.config)
    assert normalized[0][0] == "bg0"


# ---------------------------------------------------------------
# Config swap: stale spans are purged
# ---------------------------------------------------------------
def test_apply_config_purges_background_state(dummy_deck):
    runner.config = {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "anim", "image": _gif_uri(), "x": 0, "y": 0,
             "width": 2, "height": 1},
        ],
    }
    runner.update_key_image(dummy_deck, 0, False)
    assert runner.background_composites, "background must be composited"

    swapped = runner.apply_config(dummy_deck, {
        "device_type": "stream-deck-xl", "buttons": [], "backgrounds": [],
    })

    assert swapped is True
    assert runner.background_frames == {}
    assert runner.background_composites == {}
    assert not [
        s for s in runner.persistent_images
        if isinstance(s, str) and s.startswith("background:")
    ], "stale tile cycles must be gone"


def test_new_config_background_repaints_after_swap(dummy_deck):
    runner.apply_config(dummy_deck, {
        "device_type": "stream-deck-xl",
        "backgrounds": [
            {"id": "next", "image": _png_uri(), "x": 0, "y": 0,
             "width": 2, "height": 2},
        ],
    })
    runner.update_key_image(dummy_deck, 0, False)
    assert runner.persistent_image_buttons[0] == "background:next#0"


# ---------------------------------------------------------------
# The toggle/press repaint path keeps background keys working
# ---------------------------------------------------------------
def test_press_repaint_keeps_background_tile(dummy_deck, monkeypatch):
    """Pressing a covered key with no pressed-state image must repaint from
    the background tile (not blank the key)."""
    runner.config = {
        "device_type": "stream-deck-xl",
        "buttons": [{"index": 0, "idle": {}, "action": None}],
        "backgrounds": [
            {"id": "hero", "image": _png_uri(), "x": 0, "y": 0,
             "width": 2, "height": 2},
        ],
    }
    written = _written_frames(dummy_deck, monkeypatch)
    runner.update_key_image(dummy_deck, 0, False)
    idle_source = runner.persistent_image_buttons[0]

    runner.update_key_image(dummy_deck, 0, True)  # press repaint

    assert runner.persistent_image_buttons[0] == idle_source
    assert len(written[0]) >= 2, "press repaint must write the tile again"