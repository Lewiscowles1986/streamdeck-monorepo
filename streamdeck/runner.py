# runner.py — Stream Deck device runner.
# Ported from streamdeck/read_config/main.py @ 078b8b23 (repo streamdeck, main),
# extended to: load the config assigned to a device via the REST API, resolve
# a nominated agent computer for command actions, and support the dummy
# transport for hardware-free end-to-end testing.

from __future__ import annotations

import argparse
from collections.abc import Iterator
from fractions import Fraction
import itertools
import json
import base64
from pathlib import Path
import time
import requests
import threading
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageSequence

from .core.DeviceManager import DeviceManager
from .core.ImageHelpers import PILHelper
from .core.Transport.Transport import TransportError
from .agent import (
    enqueue_action as post_agent_action,
    build_agent_action,
    expand_template_vars,
)

# Animation frames per second to attempt to display on the StreamDeck devices.
FRAMES_PER_SECOND = 30

closed_event = threading.Event()
buttons: dict[int, dict] = {}
persistent_images: dict[str, Iterator | Image.Image] = {}
persistent_image_buttons: dict[int, str] = {}
# P13: pause state keyed by the full image source string (same key as
# persistent_images), so pausing holds that GIF for EVERY button showing it.
# Absent/False = playing; True = paused on the current frame.
paused_images: dict[str, bool] = {}
config: dict = {}


# -------------------------
# Cached Image Loader
# -------------------------
@lru_cache(maxsize=128)
def load_image_from_source(source: str) -> Image.Image | Iterator[Image.Image]:
    """
    Loads an image from:
       - Local filesystem
       - HTTP/HTTPS URL
       - Base64 data URI
    Returns a PIL Image.
    """
    if source.startswith("data:image"):
        # Base64 encoded image
        _, b64data = source.split(",", 1)
        return Image.open(BytesIO(base64.b64decode(b64data)))

    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    # Otherwise assume it's a local file path
    return Image.open(source.replace("file://", ""))


# -------------------------
# Rendering Helpers
# -------------------------
def resolve_font_path(family: str | None) -> Path:
    """
    Resolve a font-family name to an existing font file. Only the bundled
    Roboto ships with the package; everything else maps onto the closest
    bundled/available face so the advertised font choices render instead of
    being silently ignored.
    """
    assets = Path(__file__).parent / "assets"
    if family:
        key = family.strip().lower()
        if "mono" in key:
            for candidate in (
                Path("/System/Library/Fonts/Menlo.ttc"),
                Path("/System/Library/Fonts/Monaco.dfont"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
            ):
                if candidate.exists():
                    return candidate
        elif "serif" in key and "sans" not in key:
            for candidate in (
                Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
                Path("/System/Library/Fonts/Times.ttc"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            ):
                if candidate.exists():
                    return candidate
        # Named faces (Arial/Helvetica/Roboto/anything else): on macOS the
        # system may provide them; else fall through to the bundled Roboto.
        for name in (family, f"{family}.ttf"):
            for candidate in (assets / name, Path("/Library/Fonts") / name):
                if candidate.is_file():
                    return candidate
    bundled = assets / "Roboto-Regular.ttf"
    if bundled.exists():
        return bundled
    return assets / "Roboto-Regular.ttf"


def resolve_label_style(state_cfg: dict | None) -> dict:
    """
    Resolve the label drawing style for a button state. Defaults match the
    original hardcoded port (Roboto 14, white, bottom) so existing configs
    keep rendering identically; any ``font`` block in the state overrides.
    """
    font = (state_cfg or {}).get("font") or {}
    return {
        "family": font.get("family") or "Roboto",
        "size": font.get("size") or 14,
        "color": font.get("color") or "white",
        "weight": font.get("weight") or "normal",
        "position": font.get("position") or "bottom",
    }


def _label_anchor(position: str) -> str:
    return {"top": "ma", "center": "mm", "middle": "mm"}.get(position, "ms")


def convert_image(
    deck, img: Image.Image, label_text=None, label_style: dict | None = None
) -> bytes:
    """Convert image to native StreamDeck format."""
    margins = [0, 0, 20, 0] if label_text else [5, 5, 5, 5]
    if label_text and label_style:
        # Extra top margin when the label is drawn at the top edge.
        if label_style.get("position") == "top":
            margins = [20, 0, 0, 0]

    image = PILHelper.create_scaled_key_image(deck, img, margins=margins)

    if label_text:
        style = label_style or resolve_label_style(None)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(
            str(resolve_font_path(style["family"])), style["size"]
        )
        draw.text(
            (image.width / 2, image.height / 2),
            text=label_text,
            font=font,
            anchor=_label_anchor(style["position"]),
            fill=style["color"],
        )
    return PILHelper.to_native_key_format(deck, image)


def render_key_image(deck, image_source, label_text=None, label_style=None):
    img = load_image_from_source(image_source)

    existing = persistent_images.get(image_source)
    if existing:
        return existing

    is_sequence = any(
        [
            getattr(img, "is_animated", False),
            getattr(img, "n_frames", 1) > 1,
        ]
    )

    if is_sequence:
        icon_frames = []
        # Iterate through each animation frame of the source image
        for frame in ImageSequence.Iterator(img):
            # Create new key image of the correct dimensions, black background.
            icon_frames.append(convert_image(deck, frame, label_text, label_style))

        # Return the decoded list of frames - the caller will need to decide
        # how to sequence them for display.
        persistent_images[image_source] = itertools.cycle(icon_frames)
        return persistent_images[image_source]

    return convert_image(deck, img, label_text, label_style)


def render_key_style(btn_cfg: dict) -> dict:
    """Resolve label style for the button config that produced a render."""
    return resolve_label_style(btn_cfg)


# -------------------------
# Button Rendering Logic
# -------------------------
def get_button_config(key_index, state):
    """
    Looks up key metadata from the active config, including toggle states.
    """
    old_state = buttons.get(key_index)

    for btn in config["buttons"]:
        if btn["index"] == key_index:
            if old_state is None:
                buttons[key_index] = {"state": 0, "action": btn.get("action")}
            toggle_states = btn.get("toggleStates", None)
            has_toggle = toggle_states and len(toggle_states) > 0
            if not has_toggle:
                state_cfg = btn.get("pressed", {}) if state else btn.get("idle", {})
                # P13: the animation block is button-level (start paused /
                # initial frame), so it applies whichever state is rendered.
                if btn.get("animation"):
                    state_cfg = {**state_cfg, "animation": btn["animation"]}
                return state_cfg
            if has_toggle:
                if state and old_state:
                    new_state = (old_state["state"] + 1) % len(toggle_states)
                    buttons[key_index]["state"] = new_state
                    buttons[key_index]["action"] = toggle_states[new_state].get(
                        "action", btn.get("action")
                    )
                ret_val = btn.get("idle", {}).copy()
                ret_val.update({**toggle_states[buttons[key_index]["state"]]})
                return ret_val

    # No matching config → return a blank key
    return {"image": None, "text": None}


BLANK_IMAGE = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAAXNSR0IB2cksf"
    "wAAAARnQU1BAACxjwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAA"
    "AAlwSFlzAAAuIwAALiMBeKU/dgAAABl0RVh0Q29tbWVudABDcmVhdGVkIHdpdGggR0lNUFeBDhcAAAAnSUR"
    "BVHja7cEBDQAAAMKg909tDjegAAAAAAAAAAAAAAAAAAAAgHcDQEAAAa96DugAAAAASUVORK5CYII="
)


def update_key_image(deck, key, state):
    btn_cfg = get_button_config(key, state)

    if btn_cfg.get("image") is None:
        btn_cfg["image"] = BLANK_IMAGE

    text = btn_cfg.get("text") or ""
    label_style = resolve_label_style(btn_cfg)

    # Was this source already decoded before this call? A fresh decode is a
    # FIRST paint for a new registration and must always write; a repaint of
    # an already-registered animated source can be skipped while paused.
    was_cached = btn_cfg["image"] in persistent_images

    image = render_key_image(deck, btn_cfg["image"], text, label_style)
    if btn_cfg["image"] in persistent_images:
        persistent_image_buttons[key] = btn_cfg["image"]
        _apply_button_animation_config(btn_cfg, btn_cfg["image"])

    if (
        was_cached
        and isinstance(image, Iterator)
        and paused_images.get(btn_cfg["image"])
    ):
        # P13: this source is paused and the deck already shows the held
        # frame — neither pull (which would advance the shared cycle) nor
        # write. A paused deck keeps its frame across button presses.
        return

    with deck:
        deck.set_key_image(
            key, next(image) if isinstance(image, Iterator) else image
        )


def _apply_button_animation_config(btn_cfg: dict, source: str) -> None:
    """Apply a button's optional ``animation`` config block at registration
    time (P13). Two controls:

    - ``paused``: mark the SOURCE as paused so the animate tick holds the
      frame (pause is shared: every button showing this source holds).
    - ``frameIndex``: advance the shared cycle exactly N times BEFORE the
      first paint, best-effort (a static source has nothing to advance).
    """
    animation = btn_cfg.get("animation") or {}
    if not isinstance(animation, dict):
        return
    frame_index = animation.get("frameIndex")
    if frame_index:
        cycle = persistent_images.get(source)
        for _ in range(int(frame_index)):
            try:
                next(cycle)
            except (StopIteration, TypeError):
                break
    if animation.get("paused"):
        paused_images[source] = True


def handle_animation_action(action_name: str, key: int) -> None:
    """Resolve the image source currently shown by ``key`` and set its
    pause flag (P13). ``pause``/``play``/``toggle-animation`` map to
    True/False/flip. Sources with no entry count as playing."""
    if action_name == "toggle-animation":
        current = paused_images.get(_source_for_key(key), False)
        _set_paused_for_key(key, not current)
    elif action_name == "pause":
        _set_paused_for_key(key, True)
    elif action_name == "play":
        _set_paused_for_key(key, False)


def _source_for_key(key: int) -> str | None:
    """The image source a button currently displays (its own registration
    if present, else resolved from the config's idle/pressed image)."""
    source = persistent_image_buttons.get(key)
    if source is not None:
        return source
    btn_cfg = get_button_config(key, False)
    return btn_cfg.get("image")


def _set_paused_for_key(key: int, paused: bool) -> None:
    source = _source_for_key(key)
    if source is not None:
        paused_images[source] = paused


# -------------------------
# Actions (agent nomination)
# -------------------------
def dispatch_action(deck, key, btn_action):
    """
    Execute a button action. Command actions are routed to the nominated
    agent computer when one is set (via the API), otherwise they are logged
    for the operator. Template variables the web UI can insert are expanded
    with the runtime context known at press time (button index, device id,
    toggle state, config name).
    """
    if not isinstance(btn_action, dict) or btn_action.get("type") != "command":
        return
    device_id = deck.get_serial_number() if deck.is_open() else None

    key_state = buttons.get(key) or {}
    context = {
        "button_index": key,
        "device_id": device_id or "",
        "toggle_state": key_state.get("state", 0),
        "config_name": config.get("name", ""),
    }
    action = build_agent_action(
        action=expand_template_vars(btn_action, context),
        device_id=device_id,
        button_index=key,
    )
    try:
        post_agent_action(action)
    except Exception as err:  # keep the runner alive when no API is running
        print(f"[ACTION] dispatch failed ({err}): {btn_action}")


# -------------------------
# Key Callback
# -------------------------
def key_change_callback(deck, key, state):
    btn_action = (buttons.get(key, None) or {"action": None})["action"]
    print(f"[EVENT] Key={key} State={state}, action={str(btn_action)}")

    if key >= deck.key_count():
        return

    if btn_action == "exit" and state:
        print("Exiting application as per button action.")
        closed_event.set()
        deck.reset()
        deck.close()
        return

    # P13: animation controls. Both the bare-string form (like "exit") and
    # the {"type": ...} dict form are accepted.
    animation_action = None
    if state:
        if btn_action in ("pause", "play", "toggle-animation"):
            animation_action = btn_action
        elif isinstance(btn_action, dict) and btn_action.get("type") in (
            "pause",
            "play",
            "toggle-animation",
        ):
            animation_action = btn_action["type"]
    if animation_action:
        handle_animation_action(animation_action, key)

    if state and isinstance(btn_action, dict):
        dispatch_action(deck, key, btn_action)

    update_key_image(deck, key, state)


def parse_arguments():
    parser = argparse.ArgumentParser(description="StreamDeck Configuration Application")

    parser.add_argument(
        "--config", type=str, help="Path to an alternative JSON configuration file"
    )
    parser.add_argument(
        "--brightness", type=int, default=30, help="Set the brightness of the StreamDeck (default: 30)"
    )
    parser.add_argument(
        "--list-devices", action="store_true", help="List all connected StreamDeck devices"
    )
    parser.add_argument(
        "--device-type", type=str, help="Specify a specific StreamDeck device type to use"
    )
    parser.add_argument(
        "--ignore-device-type-check",
        action="store_true",
        help="Ignore device type matching from configuration",
    )
    parser.add_argument(
        "--api",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the configuration API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--device-id",
        type=str,
        help="Serial number of the device to drive (default: first matching deck)",
    )

    return parser.parse_args()


def fetch_assigned_config(api: str, device_id: str) -> dict | None:
    """Fetch the config currently assigned to a device from the REST API."""
    try:
        response = requests.get(f"{api}/device/{device_id}/config", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("config")
    except Exception as err:
        print(f"[API] Could not load assigned config: {err}")
    return None


# -------------------------
# Main Logic
# -------------------------
def animate_tick(deck) -> None:
    """One pass of the 30fps animate loop (P13 refactor; behavior identical
    to the former inline loop body). Pulls the next frame for every playing
    source and writes it to every button registered to show it. A PAUSED
    source is neither pulled nor written — the cycle retains its position,
    so the held frame stays on deck and resume continues from it."""
    img: dict[str, bytes] = {}
    with deck:
        for source, image in persistent_images.items():
            if isinstance(image, Iterator) and paused_images.get(source):
                continue
            img[source] = next(image)
        for key, source in persistent_image_buttons.items():
            image = img.get(source)
            if image:
                deck.set_key_image(key, image)


# -------------------------
# Main Logic
# -------------------------
def run_deck(deck, args) -> None:
    """Open and drive a single deck until closed."""
    if not deck.is_open():
        deck.open()
    deck.reset()

    print(f"Opened '{deck.deck_type()}' ({deck.get_serial_number()})")

    deck.set_brightness(args.brightness)

    # Prefer an explicitly supplied config file, then the API-assigned config,
    # else whatever global config is already loaded.
    global config
    serial = deck.get_serial_number()
    if not args.config:
        assigned = fetch_assigned_config(args.api, args.device_id or serial)
        if assigned:
            config = assigned
            print(f"[API] Using assigned config '{config.get('name')}'")

    # Initialize state
    for key in range(deck.key_count()):
        update_key_image(deck, key, False)

    def animate(fps):
        frame_time = Fraction(1, fps)
        next_frame = Fraction(time.monotonic())
        while not closed_event.is_set() and deck.is_open():
            try:
                animate_tick(deck)
            except TransportError as err:
                print(f"TransportError: {err}")
                break

            next_frame += frame_time
            sleep_interval = float(next_frame) - time.monotonic()
            if sleep_interval >= 0:
                time.sleep(sleep_interval)

    # Kick off the key image animating thread.
    threading.Thread(target=animate, args=[FRAMES_PER_SECOND], daemon=True).start()

    deck.set_key_callback(key_change_callback)

    # Block until deck closed
    while deck.is_open() and not closed_event.is_set():
        time.sleep(0.5)


def main(args) -> None:
    from .app import get_device_manager

    streamdecks = get_device_manager().enumerate()

    print(f"Found {len(streamdecks)} Stream Deck(s).\n")

    if args.list_devices:
        for deck in streamdecks:
            print(f"- {deck.deck_type()} (Serial: {deck.get_serial_number()})")
        return

    global config
    if args.config:
        try:
            with open(args.config, "r") as config_file:
                config = json.load(config_file)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error loading config file: {e}")
            return

    for deck in streamdecks:
        deck.open()

        if args.device_id and deck.get_serial_number() != args.device_id:
            print(f"Skipping deck ({deck.get_serial_number()}) - not the requested device")
            deck.close()
            continue

        if all(
            [
                deck.deck_type().lower() != config["device_type"].lower(),
                deck.deck_type().lower().replace(" ", "-") != config["device_type"].lower(),
                args.ignore_device_type_check is False,
            ]
        ):
            print(f"Skipping deck ({deck.deck_type()}) - does not match config device_type")
            deck.close()
            continue

        try:
            run_deck(deck, args)
        finally:
            if deck.is_open():
                deck.close()

    print("Exiting application.")