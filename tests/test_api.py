# test_api.py — REST API integration tests (no hardware, no network).
#
# Covers the ported surface (devices/configs CRUD + assignment) and the new
# agent endpoints (register, nominate, queue, poll, report).

from __future__ import annotations


def _make_config(name="Test Config", device_type="stream-deck-xl", buttons=None):
    return {
        "name": name,
        "deviceType": device_type,
        "buttons": buttons
        or [
            {"index": 0, "idle": {"text": "A"}, "pressed": {"text": "A!"}},
            {"index": 31, "action": "exit", "idle": {"text": "quit"}},
        ],
    }


def _pick(response_dict, snake, camel):
    """The API historically serializes with aliases (camelCase); read both."""
    return response_dict.get(snake, response_dict.get(camel))


# -----------------------------
# Configs
# -----------------------------
def test_create_get_list_delete_config(client):
    created = client.post("/config", json=_make_config()).json()
    assert created["id"]
    assert _pick(created, "device_type", "deviceType") == "stream-deck-xl"

    fetched = client.get(f"/config/{created['id']}").json()
    assert fetched["name"] == "Test Config"

    listed = client.get("/configs").json()
    assert any(c["id"] == created["id"] for c in listed)

    deleted = client.delete(f"/config/{created['id']}").json()
    assert deleted["id"] == created["id"]
    assert client.get(f"/config/{created['id']}").status_code == 404


def test_update_config(client):
    created = client.post("/config", json=_make_config()).json()
    updated = client.put(
        f"/config/{created['id']}",
        json=_make_config(name="Renamed", buttons=[{"index": 1, "idle": {"text": "B"}}]),
    ).json()
    assert updated["name"] == "Renamed"
    assert updated["buttons"][0]["index"] == 1


# -----------------------------
# Devices (dummy transport enumerates one)
# -----------------------------
def test_devices_endpoint_lists_dummy_deck(client):
    devices = client.get("/devices").json()
    assert len(devices) >= 1
    assert devices[0]["type"]


def test_assign_config_to_device(client):
    device = client.get("/devices").json()[0]
    config = client.post("/config", json=_make_config()).json()

    response = client.put(f"/device/{device['id']}/config/{config['id']}")
    assert response.status_code == 200
    assert _pick(response.json(), "current_config_id", "currentConfigId") == config["id"]

    # The runner-facing endpoint returns the assigned config and device.
    payload = client.get(f"/device/{device['id']}/config").json()
    assert payload["config"]["id"] == config["id"]
    assert payload["device"]["id"] == device["id"]


# -----------------------------
# Agents: register -> nominate -> queue -> poll -> report
# -----------------------------
def test_agent_roundtrip(client):
    device = client.get("/devices").json()[0]

    # 1. A machine registers itself
    agent = client.post(
        "/agents",
        json={"id": "agent-1", "hostname": "box.local", "platform": "Darwin"},
    ).json()
    assert agent["id"] == "agent-1"
    assert client.get("/agents").json()[0]["hostname"] == "box.local"

    # 2. The device nominates this agent
    nominated = client.put(f"/device/{device['id']}/agent/agent-1").json()
    assert _pick(nominated, "active_agent_id", "activeAgentId") == "agent-1"

    # 3. A button action is queued for the device
    queued = client.post(
        "/agent-actions",
        json={
            "agentId": "agent-1",
            "deviceId": device["id"],
            "buttonIndex": 3,
            "action": {"type": "command", "executable": "open", "arguments": "-a Finder"},
        },
    ).json()
    assert queued["status"] == "pending"

    # 4. The agent polls and receives it
    pending = client.get("/agents/agent-1/actions").json()
    assert len(pending) == 1
    polled = pending[0]
    assert polled["action"]["executable"] == "open"
    assert polled["status"] == "pending"

    # 5. Reports back the result
    action_id = pending[0]["id"]
    done = client.post(
        f"/agents/agent-1/actions/{action_id}/result",
        json={"status": "done", "returncode": 0},
    ).json()
    assert done["status"] == "done"
    # Already dispatched: a second poll sees nothing new
    assert client.get("/agents/agent-1/actions").json() == []


def test_unknown_agent_rejected(client):
    response = client.post(
        "/agent-actions",
        json={"agentId": "ghost", "action": {"type": "command", "executable": "ls"}},
    )
    assert response.status_code == 404


def test_nominate_unknown_agent_404(client):
    device = client.get("/devices").json()[0]
    assert client.put(f"/device/{device['id']}/agent/nope").status_code == 404


def test_delete_agent_clears_nomination(client):
    device = client.get("/devices").json()[0]
    client.post("/agents", json={"id": "agent-2", "hostname": "x.local"})
    client.put(f"/device/{device['id']}/agent/agent-2")
    client.delete("/agents/agent-2")
    refreshed = [d for d in client.get("/devices").json() if d["id"] == device["id"]][0]
    assert _pick(refreshed, "active_agent_id", "activeAgentId") is None