# agent.py — "nominate a computer" client.
#
# A machine runs `streamdeck agent --server http://deck-server:8000` and
# registers itself. Stream Deck buttons configured with a command action are
# routed to the agent nominated on their device; the agent polls the server,
# executes pending actions and reports results back.
#
# New in this port (user use-case): lets one Stream Deck drive several
# computers without the deck itself knowing anything about them.

from __future__ import annotations

import os
import platform
import socket
import time
import uuid
import subprocess
from pathlib import Path
from typing import Any

import requests

AGENT_ID_FILE = ".streamdeck-agent-id"

# Template variables supported inside command actions. The web UI inserts
# these tokens (see frontend TEMPLATE_VARIABLES); the agent expands them
# just before execution so the same action works on any machine.
TEMPLATE_CONTEXT_KEYS = {
    "button_index": "",
    "device_id": "",
    "toggle_state": "",
    "config_name": "",
    "timestamp": "",
    "date": "",
    "time": "",
}

# Default attached-mode timeout in seconds. A corrupt/non-numeric timeout
# in an action falls back to this rather than crashing the executor.
DEFAULT_TIMEOUT = 30


def _as_int(value: Any, fallback: int) -> int:
    """Coerce a JSON-ish value to int with a fallback (crash-safety)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_env(value: Any) -> dict:
    """Coerce an action's env field to a dict of strings; anything that
    isn't a mapping collapses to {} instead of exploding subprocess."""
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _as_cwd(value: Any) -> str | None:
    """Coerce cwd: None/empty → None; a non-directory is ignored (inherit
    the executor's cwd) rather than raising FileNotFoundError later."""
    if not isinstance(value, str) or not value:
        return None
    try:
        if Path(value).is_dir():
            return value
    except OSError:
        return None
    return None


def expand_template_vars(value: Any, context: dict[str, Any] | None = None) -> Any:
    """
    Recursively expand ``{{name}}`` template variables in a JSON-ish value.

    Supported variables (mirroring the web UI's TEMPLATE_VARIABLES):
      {{button_index}} {{device_id}} {{toggle_state}} {{config_name}}
      {{timestamp}} (unix seconds) {{date}} (YYYY-MM-DD) {{time}} (HH:MM:SS)

    Unknown variables are left untouched so literal ``{{...}}`` text in a
    command survives.
    """
    ctx = dict(context or {})
    ctx.setdefault("timestamp", str(int(time.time())))
    ctx.setdefault("date", time.strftime("%Y-%m-%d"))
    ctx.setdefault("time", time.strftime("%H:%M:%S"))

    if isinstance(value, str):
        out = value
        for key, replacement in ctx.items():
            out = out.replace("{{" + key + "}}", str(replacement))
        return out
    if isinstance(value, dict):
        return {k: expand_template_vars(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_template_vars(v, ctx) for v in value]
    return value


def _load_or_create_agent_id() -> str:
    """Persist a per-machine agent id in the user's home directory."""
    from pathlib import Path

    id_file = Path.home() / AGENT_ID_FILE
    if id_file.exists():
        agent_id = id_file.read_text(encoding="utf-8").strip()
        if agent_id:
            return agent_id
    # Stable UUID derived from hostname; readable and collision-safe enough.
    agent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
    try:
        id_file.write_text(agent_id, encoding="utf-8")
    except OSError:
        pass
    return agent_id


def register(server: str) -> dict[str, Any]:
    """Register this machine with the Stream Deck server."""
    agent = {
        "id": _load_or_create_agent_id(),
        "hostname": socket.gethostname(),
        "user": os.getenv("USER") or os.getenv("USERNAME"),
        "platform": platform.platform(),
        "active": True,
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    response = requests.post(f"{server}/agents", json=agent, timeout=10)
    response.raise_for_status()
    return response.json()


def poll_actions(server: str, agent_id: str) -> list[dict[str, Any]]:
    """Fetch and acknowledge pending actions for this agent."""
    response = requests.get(f"{server}/agents/{agent_id}/actions", timeout=30)
    if response.status_code == 404:
        # Server lost our registration (fresh database) — re-register once.
        register(server)
        return []
    response.raise_for_status()
    return response.json()


def report_result(server: str, action_id: str, result: dict[str, Any]) -> None:
    """Report an action outcome back to the server."""
    try:
        url = (
            f"{server}/agents/{_load_or_create_agent_id()}"
            f"/actions/{action_id}/result"
        )
        requests.post(url, json=result, timeout=10)
    except Exception as err:
        print(f"[AGENT] result report failed: {err}")


def execute(
    action: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Execute a command action on this machine:
    ``{"type": "command", "executable": str, "arguments": str|None, ...}``

    ``context`` supplies runtime values for the ``{{...}}`` template
    variables the web UI can insert (button index, device id, toggle state,
    config name). Time tokens are always available.

    Launch modes (P14):
      - "attached" (default): run with a timeout, wait, capture output and
        report the result — the pre-existing behavior, now named.
      - "detached": start the process WITHOUT waiting (Popen with
        start_new_session=True so it survives the agent) and report
        status "detached" with the child's pid. No timeout, no capture.

    Crash-safety contract: execute() NEVER raises. Every failure mode —
    missing executable, nonexistent cwd, corrupt env/timeout/mode, even an
    internal bug — comes back as a structured result with a "status" key,
    because this runs inside the agent's polling loop and one bad action
    must never kill the loop.
    """
    try:
        if not isinstance(action, dict):
            return {
                "status": "failed",
                "error": f"action is not an object: {action!r}",
            }

        if action.get("type") != "command":
            return {
                "status": "failed",
                "error": f"unsupported action type {action.get('type')!r}",
            }

        action = expand_template_vars(action, context)

        executable = action.get("executable")
        if not isinstance(executable, str) or not executable:
            return {"status": "failed", "error": "action has no executable"}

        argv = [executable]
        arguments = action.get("arguments")
        if isinstance(arguments, str) and arguments:
            # Arguments are a shell-style string in the config format;
            # expand them with the shell on the agent side so operators
            # can use variables.
            argv = [executable, *arguments.split()]
        elif isinstance(arguments, list):
            argv = [executable, *(str(a) for a in arguments)]
        elif arguments:
            argv = [executable, str(arguments)]

        mode = action.get("mode") or "attached"
        if mode == "detached":
            return _execute_detached(argv, action)
        return _execute_attached(argv, action)
    except Exception as err:  # never let an action kill the agent loop
        return {"status": "failed", "error": f"executor error: {err}"}


def _execute_attached(argv: list[str], action: dict[str, Any]) -> dict[str, Any]:
    """Attached launch: subprocess.run + wait + capture + report."""
    env = os.environ.copy()
    env.update(_as_env(action.get("env")))
    cwd = _as_cwd(action.get("cwd"))
    timeout = _as_int(action.get("timeout", DEFAULT_TIMEOUT), DEFAULT_TIMEOUT)

    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "status": "done" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except Exception as err:
        return {"status": "failed", "error": str(err)}


def _execute_detached(argv: list[str], action: dict[str, Any]) -> dict[str, Any]:
    """Detached launch (P14): Popen without waiting, disowned into its own
    session so the child survives the agent stopping. No output capture,
    no timeout kill. Any start failure comes back as a failed result."""
    env = os.environ.copy()
    env.update(_as_env(action.get("env")))
    cwd = _as_cwd(action.get("cwd"))

    try:
        process = subprocess.Popen(  # noqa: S603
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"status": "detached", "pid": process.pid}
    except Exception as err:
        return {"status": "failed", "error": str(err)}


# -------------------------
# Server-side helper (used by the device runner)
# -------------------------
def build_agent_action(action: dict, device_id: str | None, button_index: int) -> dict:
    """Wrap a button action into an AgentAction payload for the queue API."""
    return {
        "agentId": "",  # resolved from the device nomination by the runner
        "buttonIndex": button_index,
        "deviceId": device_id,
        "action": action,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def enqueue_action(action: dict) -> dict:
    """
    Send a button action to the API. The server resolves the nominated agent
    from the device (active_agent_id); when the action already carries an
    agent_id it is used verbatim (direct agent -> queue usage).
    """
    api = os.getenv("STREAMDECK_API", "http://localhost:8000")
    agent_id = action.get("agentId") or _resolve_agent_for_device(action)
    payload = {**action, "agentId": agent_id}
    response = requests.post(f"{api}/agent-actions", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def _resolve_agent_for_device(action: dict) -> str | None:
    device_id = action.get("deviceId")
    if not device_id:
        return None
    api = os.getenv("STREAMDECK_API", "http://localhost:8000")
    response = requests.get(f"{api}/device/{device_id}/config", timeout=5)
    device = response.json().get("device") if response.ok else None
    if not device:
        return None
    return device.get("activeAgentId") or device.get("active_agent_id")


# -------------------------
# Agent main loop
# -------------------------
def agent_loop(server: str, interval: float = 5.0) -> None:  # noqa: C901
    agent_id = _load_or_create_agent_id()
    print(f"[AGENT] registering {agent_id} at {server}")
    register(server)

    print("[AGENT] polling for actions; Ctrl-C to stop")
    while True:
        try:
            for item in poll_actions(server, agent_id):
                print(f"[AGENT] executing action {item['id']} ({item.get('action')})")
                result = execute(item.get("action") or {})
                report_result(server, item["id"], result)
                print(f"[AGENT] result: {result.get('status')}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("[AGENT] stopping")
            return
        except Exception as err:
            print(f"[AGENT] poll error: {err}")
            time.sleep(max(interval, 5))