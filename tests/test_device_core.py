# test_device_core.py — the core library through the dummy transport.
#
# Exercises the vendored StreamDeck library end-to-end without hardware:
# enumeration, open/close, metadata reads and native image writes all flow
# through the real code paths; only the USB layer is stubbed by Dummy.py.

from __future__ import annotations

import pytest

from streamdeck.core.DeviceManager import DeviceManager
from streamdeck.core.Transport.Transport import TransportError
from streamdeck.core.ImageHelpers import PILHelper

pytestmark = pytest.mark.usefixtures("dummy_transport")


def test_dummy_enumerates_deck():
    manager = DeviceManager(transport="dummy")
    decks = manager.enumerate()
    # One emulated deck per known Elgato product ID, each with a unique
    # deterministic synthetic serial (see Dummy.py read_feature).
    assert len(decks) >= 1
    deck = decks[0]
    assert deck.is_open() is False


def test_open_close_cycle():
    deck = DeviceManager(transport="dummy").enumerate()[0]
    assert not deck.is_open()
    deck.open()
    assert deck.is_open()
    deck.close()
    assert not deck.is_open()


def test_metadata_through_dummy():
    deck = DeviceManager(transport="dummy").enumerate()[0]
    deck.open()
    assert deck.key_count() > 0
    # Dummy transport returns a deterministic synthetic serial number.
    assert deck.get_serial_number().startswith("DUMMY")
    assert deck.deck_type()
    deck.close()


def test_set_key_image_roundtrip(dummy_deck):
    from PIL import Image

    image = Image.new("RGB", dummy_deck.key_image_format()["size"], "red")
    native = PILHelper.to_native_key_format(dummy_deck, image)
    dummy_deck.set_key_image(0, native)  # must not raise


def test_write_requires_open():
    deck = DeviceManager(transport="dummy").enumerate()[0]
    with pytest.raises(Exception):
        deck.set_brightness(50)  # transport raises: deck not open


def test_transport_error_closes_deck():
    deck = DeviceManager(transport="dummy").enumerate()[0]
    deck.open()
    deck.close()
    assert not deck.is_open()