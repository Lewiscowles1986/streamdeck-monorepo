# test_hardware.py — OPT-IN hardware smoke test.
#
# Run only when a physical Stream Deck is attached:
#   STREAMDECK_TRANSPORT=libusb .venv/bin/python -m pytest -m hardware tests/test_hardware.py
#
# Never runs in CI; deselected by default via pyproject markers.

from __future__ import annotations

import pytest

from streamdeck.core.DeviceManager import DeviceManager

pytestmark = pytest.mark.hardware


def _real_decks():
    manager = DeviceManager()  # auto-probe real transports
    return manager.enumerate()


@pytest.fixture(scope="module")
def real_deck():
    decks = _real_decks()
    if not decks:
        pytest.skip("No physical Stream Deck attached")
    deck = decks[0]
    deck.open()
    yield deck
    deck.close()


def test_deck_enumerates(real_deck):
    assert real_deck.deck_type()
    assert real_deck.get_serial_number()
    assert real_deck.is_open()


def test_deck_metadata(real_deck):
    assert real_deck.key_count() > 0
    fmt = real_deck.key_image_format()
    assert fmt["size"][0] > 0 and fmt["size"][1] > 0


def test_render_and_display(real_deck):
    from PIL import Image, ImageDraw

    from streamdeck.core.ImageHelpers import PILHelper

    size = real_deck.key_image_format()["size"]
    image = Image.new("RGB", size, (16, 16, 16))
    draw = ImageDraw.Draw(image)
    draw.text((size[0] / 2, size[1] / 2), "E2E", fill="white", anchor="mm")

    native = PILHelper.to_native_key_format(real_deck, image)
    real_deck.set_key_image(0, native)


def test_brightness_roundtrip(real_deck):
    real_deck.set_brightness(50)
    real_deck.set_brightness(30)


def test_full_stack_with_hardware(client, real_deck):
    """API + real device: /devices must report the attached deck connected."""
    devices = client.get("/devices").json()
    serials = {d["id"] for d in devices}
    assert real_deck.get_serial_number() in serials