#!/usr/bin/env python3
"""hardware-tour.py — interactive real-deck evaluation tour (operator TUI).

Turns the attached Stream Deck into a self-guided evaluation surface: three
built-in "pages" exercise the features an operator cares about (labels,
press feedback, animation + pause/play, toggles, page switching,
brightness), driven by the keys themselves. The terminal mirrors the tour
and offers manual controls, so an operator can evaluate a deck without the
API, the web UI, or any config files.

Run it from the monorepo root (the venv has Pillow + the vendored core):

    STREAMDECK_TRANSPORT=libusb .venv/bin/python scripts/hardware-tour.py

Terminal controls:  n/p = next/previous page · 1-9 = jump to page
                    b / B = brightness up/down · q = quit
Everything else happens on the deck: press the on-deck page arrows, the
exit key, the animation pause/play key, the toggle.

Docs: docs/site/how-to/real-hardware.md (Step 5).
"""

from __future__ import annotations

import threading
import time
from fractions import Fraction

from PIL import Image, ImageDraw, ImageFont

from streamdeck.core.DeviceManager import DeviceManager
from streamdeck.core.ImageHelpers import PILHelper

FRAMES_PER_SECOND = 30
PAGES = ("Welcome", "Animation", "Toggle & jump")

# -------------------------
# Tour state
# -------------------------
current_page = 0
closed_event = threading.Event()
brightness = 50
anim_paused = False
anim_frame = 0
toggle_on = False
press_test_down = False

# Per-page button maps, filled once the deck (and its key count) is known.
# Each entry: (label, sublabel, bg_rgb, on_press(key, state) -> None).
page_buttons: list[dict[int, tuple]] = []
page_images: list[dict[int, Image.Image]] = []


# -------------------------
# Rendering helpers
# -------------------------
def _font(px: int) -> ImageFont.FreeTypeFont:
    import streamdeck

    bundled = (
        __import__("pathlib").Path(streamdeck.__file__).parent
        / "assets"
        / "Roboto-Regular.ttf"
    )
    if bundled.is_file():
        return ImageFont.truetype(str(bundled), px)
    return ImageFont.load_default()


def make_key_image(deck, label, sub=None, bg=(32, 32, 36), fg=(240, 240, 240)):
    """Render a text label (plus optional sub-label) to a native key image."""
    size = deck.key_image_format()["size"]
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    main = _font(max(size[0] // 7, 10))
    if sub:
        small = _font(max(size[0] // 12, 8))
        draw.text((size[0] / 2, size[1] * 0.40), label, font=main, fill=fg, anchor="mm")
        draw.text(
            (size[0] / 2, size[1] * 0.72), sub, font=small, fill=(180, 180, 190),
            anchor="mm",
        )
    else:
        draw.multiline_text(
            (size[0] / 2, size[1] / 2), label, font=main, fill=fg, anchor="mm",
            align="center",
        )
    return img


def make_animation_frames(deck, count=12):
    """A synthetic 'animated GIF' — a rotating bar + frame counter — so the
    operator can SEE frames advance (and hold) without any asset file."""
    size = deck.key_image_format()["size"]
    frames = []
    for i in range(count):
        img = Image.new("RGB", size, (16, 16, 24))
        draw = ImageDraw.Draw(img)
        w, h = size
        steps = 12
        x0 = int(w * i / steps)
        draw.rectangle([x0, 0, x0 + max(w // 6, 4), h], fill=(0, 130, 255))
        draw.ellipse(
            [w * 0.30, h * 0.30, w * 0.70, h * 0.70], outline=(255, 200, 0), width=3
        )
        draw.text(
            (w / 2, h / 2), f"{i}", font=_font(h // 4), fill=(255, 255, 255),
            anchor="mm",
        )
        frames.append(img)
    return frames


def paint(deck, key, image):
    native = PILHelper.to_native_key_format(deck, image)
    with deck:
        deck.set_key_image(key, native)


def paint_page(deck):
    """Render every key of the current page; blank the rest."""
    size = deck.key_image_format()["size"]
    blank = Image.new("RGB", size, (12, 12, 12))
    for key in range(deck.key_count()):
        entry = page_buttons[current_page].get(key)
        if entry:
            label, sub, bg, _ = entry
            paint(deck, key, make_key_image(deck, label, sub, bg))
        else:
            paint(deck, key, blank)
    print(f"[PAGE] {current_page + 1}/3 — {PAGES[current_page]}")


# -------------------------
# Page actions (on-deck)
# -------------------------
def go_next(deck, key, state):
    if state:
        switch_page(deck, (current_page + 1) % len(PAGES))


def go_prev(deck, key, state):
    if state:
        switch_page(deck, (current_page - 1) % len(PAGES))


def exit_tour(deck, key, state):
    if state:
        print("[EXIT] exit key pressed — leaving the tour")
        closed_event.set()


def brightness_step(deck, key, state, delta):
    if state:
        set_brightness(deck, brightness + delta)


def set_brightness(deck, value):
    global brightness
    brightness = max(1, min(100, value))
    try:
        deck.set_brightness(brightness)
        print(f"[BRIGHTNESS] {brightness}%")
    except Exception as err:
        print(f"[BRIGHTNESS] failed: {err}")


def press_test(deck, key, state):
    """Repaints itself on press AND release — proves the press pipeline."""
    global press_test_down
    press_test_down = state
    paint(
        deck, key,
        make_key_image(
            deck, "Pressed!" if state else "Press me",
            "release to flip" if state else None,
            (200, 60, 30) if state else (32, 32, 32),
        ),
    )


def pause_play(deck, key, state):
    global anim_paused
    if state:
        anim_paused = not anim_paused
        paint(
            deck, key,
            make_key_image(
                deck, "Play ▶" if anim_paused else "Pause ⏸", None,
                (30, 90, 40) if anim_paused else (90, 60, 10),
            ),
        )
        print(f"[ANIMATION] {'paused (frame held)' if anim_paused else 'playing'}")


def toggle_flip(deck, key, state):
    global toggle_on
    if state:
        toggle_on = not toggle_on
        paint(
            deck, key,
            make_key_image(
                deck, "ON" if toggle_on else "OFF", "toggle",
                (40, 140, 70) if toggle_on else (60, 60, 60),
            ),
        )
        print(f"[TOGGLE] {'ON' if toggle_on else 'OFF'}")


# -------------------------
# Pages
# -------------------------
def build_pages(deck):
    kc = deck.key_count()
    exit_key, next_key, prev_key = kc - 1, None, None
    if kc >= 8:
        next_key, prev_key = kc - 2, kc - 3
    controls = {
        exit_key: ("Exit ⏏", "quit tour", (150, 40, 40), exit_tour),
    }
    if next_key is not None:
        controls[next_key] = ("Next ▶", "switch page", (40, 60, 150), go_next)
        controls[prev_key] = ("◀ Prev", "switch page", (40, 60, 150), go_prev)

    def jump_to(page):
        def action(deck_, key, state):
            if state:
                switch_page(deck_, page)

        return action

    welcome = {
        0: ("Welcome", f"page 1/{len(PAGES)}", (30, 30, 60), None),
        1: ("Press me", "press pipeline", (32, 32, 32), press_test),
        2: ("Bright +", "brightness +10", (50, 50, 30), lambda d, k, s: brightness_step(d, k, s, +10)),
        3: ("Bright −", "brightness -10", (50, 50, 30), lambda d, k, s: brightness_step(d, k, s, -10)),
        **controls,
    }
    animation = {
        0: ("30 fps", "animated frames", (16, 16, 24), None),
        1: ("Pause ⏸", "hold the frame", (90, 60, 10), pause_play),
        2: ("Static", "no animation", (32, 32, 32), None),
        **controls,
    }
    toggles = {
        0: ("OFF", "toggle", (60, 60, 60), toggle_flip),
        1: ("Go p1", "jump to page 1", (40, 60, 150), jump_to(0)),
        **controls,
    }
    return [welcome, animation, toggles]


def switch_page(deck, page):
    global current_page, anim_paused, anim_frame, toggle_on, press_test_down
    current_page = page % len(PAGES)
    # Per-page demo state resets on entry (the tour shows state machines,
    # not persistence — persistence belongs to the real runner).
    anim_paused, anim_frame = False, 0
    toggle_on, press_test_down = False, False
    paint_page(deck)


# -------------------------
# Threads
# -------------------------
def animate(deck, frames):
    """Write the next animation frame while the Animation page is showing
    and its source is playing — the operator sees the frame counter move."""
    frame_time = Fraction(1, 30)
    next_frame = Fraction(time.monotonic())
    global anim_frame
    while not closed_event.is_set():
        if current_page == 1 and not anim_paused:
            paint(deck, 0, frames[anim_frame % len(frames)])
            anim_frame += 1
        next_frame += frame_time
        sleep = float(next_frame) - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)


def terminal_controls(deck):
    """Read one command per line; EOF (piped/closed stdin) just ends this
    helper — the on-deck keys keep working."""
    print(
        "\nTerminal controls: n/p page · 1-9 jump · b/B brightness · q quit\n"
        "Everything else happens ON THE DECK (arrows, exit, pause, toggle).\n"
    )
    while not closed_event.is_set():
        try:
            line = input("tour> ").strip()
        except EOFError:
            return
        if line in ("q", "quit", "exit"):
            closed_event.set()
        elif line == "n":
            switch_page(deck, (current_page + 1) % len(PAGES))
        elif line == "p":
            switch_page(deck, (current_page - 1) % len(PAGES))
        elif line.isdigit() and 1 <= int(line) <= len(PAGES):
            switch_page(deck, int(line) - 1)
        elif line == "b":
            set_brightness(deck, brightness + 10)
        elif line == "B":
            set_brightness(deck, brightness - 10)
        elif line == "":
            pass
        else:
            print("n/p · 1-9 · b/B · q")


# -------------------------
# Main
# -------------------------
def main() -> None:
    decks = DeviceManager().enumerate()
    if not decks:
        print("No Stream Deck attached — nothing to tour.")
        raise SystemExit(1)
    deck = decks[0]
    try:
        deck.open()
    except Exception as err:
        print(f"Could not open the deck: {err}\n"
              "macOS hint: macOS HID opens are EXCLUSIVE — close the official\n"
              "Elgato app (or any other process holding the deck) and retry.")
        raise SystemExit(1)

    print(f"Opened {deck.deck_type()} ({deck.get_serial_number()}, "
          f"{deck.key_count()} keys) — brightness {brightness}%")

    global page_buttons
    page_buttons = build_pages(deck)
    anim_frames = make_animation_frames(deck)

    deck.set_brightness(brightness)
    paint_page(deck)

    def on_key(deck_, key, state):
        entry = page_buttons[current_page].get(key)
        print(f"[EVENT] page={PAGES[current_page]} key={key} state={state}")
        if entry and entry[3]:
            try:
                entry[3](deck_, key, state)
            except Exception as err:
                print(f"[EVENT] action failed (tour survives): {err}")

    deck.set_key_callback(on_key)

    threading.Thread(target=animate, args=(deck, anim_frames), daemon=True).start()
    threading.Thread(target=terminal_controls, args=(deck,), daemon=True).start()

    try:
        while not closed_event.is_set() and deck.is_open():
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n[EXIT] Ctrl+C — leaving the tour")
    finally:
        closed_event.set()
        try:
            deck.reset()
            deck.close()
        except Exception:
            pass
        print("Tour ended. Deck reset and closed.")


if __name__ == "__main__":
    main()