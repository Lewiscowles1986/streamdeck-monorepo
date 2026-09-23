#!/usr/bin/env python3
"""tour-via-cli.py — config-driven tour installer (CLI-only tour setup).

Builds three "page" configs in the API (the exact surface the runner's
switch-config reads), wires them to each other, assigns page 1 to the
first matching deck, and prints the `streamdeck run` command to complete
the tour. Every feature that hardware-tour.py demonstrates on its own
(pages, press states, pause/play, toggles, exit) is expressed here as
config JSON consumed by the stock CLI — no custom deck-driving code.

Usage:
    .venv/bin/python scripts/tour-via-cli.py          # uses libusb deck

Requires `streamdeck serve` running (API :8000) — it creates + assigns
the configs through REST, exactly as the web UI would.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import requests

API = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "assets" / "tour"

# -------------------------
# Shared pieces
# -------------------------
FONT = {"family": "Roboto", "size": 14}
FONT_SMALL = {"family": "Roboto", "size": 10}


def counter_data_uri() -> str:
    """A 4-frame animated GIF (data URI) — the config-file equivalent of the
    tour's animated frame counter; frame HOLD/RESUME is visible on it."""
    gif = OUT / "counter.gif"
    if gif.is_file():
        return "data:image/gif;base64," + base64.b64encode(gif.read_bytes()).decode()
    # Fall back to the e2e fixture if the generated asset is missing.
    alt = OUT.parent.parent / "e2e" / "assets" / "tri-color.gif"
    return "data:image/gif;base64," + base64.b64encode(alt.read_bytes()).decode()


def make_page1() -> dict:
    return {
        "name": "Tour 1 — Welcome",
        "deviceType": "stream-deck-xl",
        "buttons": [
            {"index": 0, "idle": {"text": "Welcome", "font": FONT}},
            {
                "index": 1,
                "idle": {"text": "Press me", "font": FONT},
                "pressed": {"text": "Pressed!", "font": FONT},
            },
            {"index": 2, "idle": {"text": "cmd: true"},
             "action": {"type": "command", "executable": "/usr/bin/true",
                        "mode": "detached"}},
            {
                "index": 3,
                "isToggle": True,
                "toggleStates": [
                    {"text": "OFF", "font": FONT},
                    {"text": "ON", "font": FONT},
                ],
            },
        ],
    }


def make_page2(config1_id: str) -> dict:
    return {
        "name": "Tour 2 — Animation",
        "deviceType": "stream-deck-xl",
        "buttons": [
            {"index": 0, "idle": {"image": counter_data_uri(), "text": "30fps"}},
            {"index": 1, "idle": {"text": "Pause"}, "action": "pause"},
            {"index": 2, "idle": {"text": "Play"}, "action": "play"},
            {"index": 3, "idle": {"text": "Flip"}, "action": "toggle-animation"},
            {"index": 4, "idle": {"image": counter_data_uri()},
             "animation": {"paused": True}},
            {"index": 5, "idle": {"text": "seq demo"},
             "action": {
                 "type": "sequence",
                 "steps": [
                     {"type": "command", "executable": "/usr/bin/true"},
                     {"type": "command", "executable": "/usr/bin/true"},
                 ],
                 "stopOnError": True,
             }},
        ],
    }


def make_page3(config1_id: str, config2_id: str) -> dict:
    return {
        "name": "Tour 3 — Pages & exit",
        "deviceType": "stream-deck-xl",
        "buttons": [
            {"index": 0, "idle": {"text": "Pages", "font": FONT}},
            {"index": 1, "idle": {"text": "> p1"},
             "action": f"switch-config:{config1_id}"},
            {"index": 2, "idle": {"text": "> p2"},
             "action": f"switch-config:{config2_id}"},
            {"index": 31, "idle": {"text": "Exit", "font": FONT}, "action": "exit"},
        ],
    }


def post_config(payload: dict) -> str:
    r = requests.post(f"{API}/config", json=payload, timeout=10)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"[API] created '{payload['name']}' -> {cid}")
    return cid


def patch_switch(config_id: str, page: dict) -> None:
    """switch-config needs the OTHER configs' ids, so pages 2/3 are created
    first, then page 1's Next button is patched with page 2's id. PUT takes
    a full row (name/deviceType/buttons) — partial bodies 500."""
    r = requests.put(f"{API}/config/{config_id}", json=page, timeout=10)
    r.raise_for_status()
    print(f"[API] patched switch button on '{config_id[:8]}…'")


def first_deck_serial() -> str | None:
    r = requests.get(f"{API}/devices", timeout=10)
    r.raise_for_status()
    for d in r.json():
        if d.get("connected"):
            return d["id"]
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    p1, p2, p3 = make_page1(), None, None

    id1 = post_config(p1)
    p2 = make_page2(id1)
    id2 = post_config(p2)
    p3 = make_page3(id1, id2)
    id3 = post_config(p3)

    # Wire page 1's "Next" button to page 2 (created after page 1, so this
    # is a PATCH — the only cross-page id that cannot be known up front).
    p1["buttons"].append(
        {"index": 28, "idle": {"text": "Next > p2", "font": FONT},
         "action": f"switch-config:{id2}"}
    )
    patch_switch(id1, p1)

    # Page 2 gets Next -> page 3 and an Exit too (a full self-guided loop).
    p2["buttons"].append(
        {"index": 28, "idle": {"text": "Next > p3", "font": FONT},
         "action": f"switch-config:{id3}"}
    )
    p2["buttons"].append(
        {"index": 31, "idle": {"text": "Exit", "font": FONT}, "action": "exit"}
    )
    patch_switch(id2, p2)

    serial = first_deck_serial()
    if not serial:
        print("[API] no connected device found — assign manually in the UI")
        print(f"       page1 id: {id1}")
        return 1
    r = requests.put(f"{API}/device/{serial}/config/{id1}", timeout=10)
    r.raise_for_status()
    print(f"[API] assigned Tour 1 to device {serial}")

    print("\nNow run (the runner applies the assigned config and the tour\n"
          "is entirely CLI + config files):\n")
    print(f"  STREAMDECK_TRANSPORT=libusb .venv/bin/python -m streamdeck.cli run "
          f"--device-id {serial}\n")
    print("What to press:")
    print("  key1  press/release  -> 'Pressed!' on press (press pipeline)")
    print("  key2  detached command fires (fire-and-forget)")
    print("  key3  OFF/ON toggle cycles each press")
    print("  key28 switch to Tour 2 (pages)")
    print("  key31 exit the runner")
    print("  On Tour 2: key0 GIF animates; Pause/Play/Flip hold/resume it;")
    print("             key4 starts PAUSED (animation.paused=true);")
    print("             key5 runs a 2-step sequence; Next/Exit as above.")
    print("  On Tour 3: jump to either page; exit from here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())