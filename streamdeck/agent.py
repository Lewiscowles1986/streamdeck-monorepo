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


def execute(action: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a command action on this machine:
    ``{"type": "command", "executable": str, "arguments": str|None, ...}``
    """
    if action.get("type") != "command":
        return {"status": "failed", "error": f"unsupported action type {action.get('type')!r}"}

    executable = action.get("executable")
    if not executable:
        return {"status": "failed", "error": "action has no executable"}

    argv = [executable]
    arguments = action.get("arguments")
    if arguments:
        # Arguments are a shell-style string in the config format; expand them
        # with the shell on the agent side so operators can use variables.
        try:
            argv = [executable, *arguments.split()]
        except Exception:
            argv = [executable, arguments]

    env = os.environ.copy()
    env.update(action.get("env") or {})
    cwd = action.get("cwd") or None

    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=action.get("timeout", 30),
        )
        return {
            "status": "done" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
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