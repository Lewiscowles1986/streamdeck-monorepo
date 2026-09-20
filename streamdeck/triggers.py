# triggers.py — automatic config switching (R5, parity rule P16).
#
# A config may carry an optional `triggers` block:
#
#     {"app": ["Slack"], "network": {"ssid": "HomeWifi", "interface": "en0"}}
#
# The device runner polls this module's probes (~5s); when the probed
# environment matches a trigger of the CURRENT config, the config is
# (re)applied — see TriggerWatcher and runner.apply_config.
#
# Crash-safety contract (same spirit as the agent executor): probes run on
# a timer inside the runner, so NO probe may raise — every failure mode
# (timeout, non-zero exit, garbage output, non-macOS) returns None. The
# pure evaluator treats malformed trigger dicts as no-match instead of
# raising, because triggers arrive as schema-less JSON over the wire.

from __future__ import annotations

import platform
import subprocess
import threading


# How long a probe subprocess may run before we give up on it (seconds).
PROBE_TIMEOUT = 2

# Default wireless interface probed for the SSID (macOS).
DEFAULT_WIFI_INTERFACE = "en0"


def _on_macos() -> bool:
    return platform.system() == "Darwin"


def get_frontmost_app() -> str | None:
    """The name of the current frontmost application (macOS), via System
    Events. Returns None on non-macOS or any failure — a None result is
    "unknown", which never matches a trigger."""
    if not _on_macos():
        return None
    script = (
        'tell application "System Events" to get name of '
        "first process whose frontmost is true"
    )
    try:
        completed = subprocess.run(  # noqa: S603
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
        )
        if completed.returncode != 0:
            return None
        name = (completed.stdout or "").strip()
        return name or None
    except Exception:  # timeout, missing osascript, anything at all
        return None


def get_wifi_ssid(interface: str = DEFAULT_WIFI_INTERFACE) -> str | None:
    """The SSID of the given wireless interface (macOS), parsed from
    `ipconfig getsummary` — the modern source of truth (macOS 14+); the
    old `airport -I` path is deprecated/removed on Sequoia and is NOT
    used here. Returns None on non-macOS or any failure (no such
    interface, not on wifi, timeout)."""
    if not _on_macos():
        return None
    try:
        completed = subprocess.run(  # noqa: S603
            ["ipconfig", "getsummary", interface],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
        )
        if completed.returncode != 0:
            return None
        # getsummary prints lines like " SSID : HomeWifi_5G". Parse
        # line-by-line (first match wins) instead of one big regex so a
        # multi-line mess cannot blow up.
        for line in (completed.stdout or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("SSID") and ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                if value and value != "<ssid>":  # associated-but-hidden wifi
                    return value
                return None
        return None
    except Exception:  # timeout, missing ipconfig, anything at all
        return None


def evaluate_triggers(triggers: dict | None, context: dict) -> bool:
    """PURE decision function (no I/O): should the config this `triggers`
    block belongs to be applied given the probed `context`?

    context = {"frontmost_app": str | None, "wifi_ssid": str | None}

    Semantics:
      - app branch: True when frontmost_app matches ANY listed name,
        case-insensitively.
      - network branch: True when wifi_ssid equals the trigger ssid.
        A None probe value never matches (unknown ≠ match).
      - branches combine as OR; an empty/missing/malformed block is False.
    Malformed input never raises — triggers are user JSON.
    """
    if not isinstance(triggers, dict):
        return False

    frontmost = context.get("frontmost_app")
    wifi_ssid = context.get("wifi_ssid")

    app_list = triggers.get("app")
    if isinstance(app_list, list) and isinstance(frontmost, str) and frontmost:
        for candidate in app_list:
            if (
                isinstance(candidate, str)
                and candidate.strip().lower() == frontmost.strip().lower()
            ):
                return True

    network = triggers.get("network")
    if (
        isinstance(network, dict)
        and isinstance(wifi_ssid, str)
        and wifi_ssid
    ):
        ssid = network.get("ssid")
        if isinstance(ssid, str) and ssid.strip() == wifi_ssid.strip():
            return True

    return False


class TriggerWatcher:
    """Polls the current config's triggers and applies the config when
    they match (R5). All seams are injectable for testing:

      - get_config_fn() -> current config dict (may mutate between polls,
        e.g. after a user switch or an API assign)
      - apply_fn(config) -> the swap + re-render (runner.apply_config)
      - should_continue_fn() -> False stops the loop (runner: closed_event
        or a closed deck)
      - probe_frontmost / probe_wifi default to the real macOS probes;
        tests inject fakes. A probe may return None (unknown) or raise —
        both are treated as no-match, never propagated.
      - poll_seconds: cadence of the loop.

    Semantics (P16): triggers apply ONLY when the current config has a
    (non-empty) triggers block; a user press (switch-config) or API assign
    naturally re-aims the watcher at the new config. A matched config is
    applied ONCE — while the trigger still holds, the loop does not
    re-apply on every poll (apply-once guard; apply_fn is idempotent in
    practice, but the guard keeps re-renders off the 5s hot path).
    """

    def __init__(
        self,
        get_config_fn,
        apply_fn,
        poll_seconds: float = 5.0,
        should_continue_fn=None,
        probe_frontmost=None,
        probe_wifi=None,
    ) -> None:
        self.get_config_fn = get_config_fn
        self.apply_fn = apply_fn
        self.poll_seconds = poll_seconds
        self.should_continue_fn = should_continue_fn or (lambda: True)
        self.probe_frontmost = probe_frontmost or get_frontmost_app
        self.probe_wifi = probe_wifi or (lambda: get_wifi_ssid())
        self.thread: threading.Thread | None = None
        self._last_applied: str | None = None  # config name of last apply

    def _probe(self, probe_fn, key: str) -> str | None:
        """Run one probe; any failure is "unknown" (None), never an
        exception escaping the loop."""
        if probe_fn is None:
            return None
        try:
            return probe_fn()
        except Exception as err:  # noqa: BLE001 — probes must not kill us
            print(f"[TRIGGER] probe {key} failed ({err}): treating as no-match")
            return None

    def _tick(self) -> None:
        """One poll: read triggers, probe, evaluate, apply once."""
        cfg = self.get_config_fn()
        triggers = (cfg or {}).get("triggers") if isinstance(cfg, dict) else None
        if not isinstance(triggers, dict) or not triggers:
            return

        context = {
            "frontmost_app": self._probe(self.probe_frontmost, "frontmost"),
            "wifi_ssid": self._probe(self.probe_wifi, "wifi"),
        }
        if not evaluate_triggers(triggers, context):
            return

        # Apply-once guard: a matched config is applied once — while the
        # trigger still holds, subsequent polls must not re-apply the same
        # config (the re-render would churn the deck every poll). The
        # guard resets naturally when the CURRENT config changes (a user
        # press or API assign) or the trigger stops matching.
        applied_key = str((cfg or {}).get("name"))
        if applied_key == self._last_applied:
            return
        try:
            self.apply_fn(cfg)
            self._last_applied = applied_key
        except Exception as err:  # noqa: BLE001 — apply must not kill us
            print(f"[TRIGGER] apply failed ({err}); will retry next poll")

    def run(self) -> None:
        """The loop: poll → tick → sleep, until should_continue_fn is
        False. Every failure inside a tick is contained. The WHOLE loop
        body sits inside one final guard (JUDGE R5): should_continue_fn
        itself is called OUTSIDE the per-tick try (in the while and the
        sleep slices), so an exploding should_continue_fn (say,
        deck.is_open() blowing up) must be logged and end the watcher —
        never propagate out of run() on its thread. The deck loop is a
        separate thread and keeps running regardless."""
        try:
            while self.should_continue_fn():
                try:
                    self._tick()
                except Exception as err:  # noqa: BLE001 — belt and braces
                    print(f"[TRIGGER] watcher tick error (survives): {err}")
                # Sleep in small slices so a stop request is honored promptly.
                remaining = self.poll_seconds
                slice_size = 0.1
                while remaining > 0 and self.should_continue_fn():
                    time_slice = min(slice_size, remaining)
                    _sleep(time_slice)
                    remaining -= time_slice
        except Exception as err:  # noqa: BLE001 — a dead watcher must be
            # loud in the log and harmless to the runner: the deck loop is
            # independent (different thread) and closed_event is untouched.
            print(
                "[TRIGGER] watcher stopped by unexpected error "
                f"(deck keeps running): {err}"
            )

    def start(self) -> threading.Thread:
        """Run the loop on a daemon thread (must not hold the process
        open when the runner exits)."""
        self.thread = threading.Thread(
            target=self.run, name="streamdeck-trigger-watcher", daemon=True
        )
        self.thread.start()
        return self.thread


def _sleep(seconds: float) -> None:
    import time as _time

    _time.sleep(seconds)