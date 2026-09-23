# app.py — FastAPI application for the Stream Deck control stack.
# Ported from streamdeck/api/app.py @ 078b8b23 (repo streamdeck, main),
# with added agent endpoints (nominating a computer) and transport selection.

from __future__ import annotations

import asyncio
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .core.DeviceManager import DeviceManager, ProbeError
from .core.Transport.Dummy import Dummy
from .models import StreamDeckConfig, StreamDeckDevice, Agent, AgentAction
from .db import get_session, init_db

app = FastAPI(
    title="Stream Deck Configuration API",
    version="1.0.0",
    description=(
        "REST API for managing Elgato Stream Deck devices, configurations "
        "and nominated agent computers."
    ),
)

origins = ["http://localhost:8080", "http://localhost:8081", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Transport selection
# -----------------------------
def get_device_manager() -> DeviceManager:
    """
    Create a DeviceManager using the transport named by the
    STREAMDECK_TRANSPORT environment variable ("libusb" by default,
    "dummy" for hardware-free end-to-end testing).
    """
    transport = os.getenv("STREAMDECK_TRANSPORT", "libusb").lower()
    if transport == "dummy":
        return DeviceManager(transport="dummy")
    return DeviceManager()  # auto-probe real transports


# -----------------------------
# Utility to convert device metadata
# -----------------------------
def get_device_metadata(deck):
    deck.open()  # Required to read serial number + device info

    serial_number = deck.get_serial_number()
    deck_type = deck.deck_type()

    deck.close()

    return StreamDeckDevice(
        id=serial_number,
        type=deck_type,
        name=f"{deck_type} - {serial_number}",
        connected=False,
        current_config_id=None,
    )


def list_device_metadata():
    """
    Enumerate decks and return their metadata without DB side effects.
    Each deck is opened only to read its serial number and type, then closed;
    values are captured while open so callers can print them safely.
    """
    infos = []
    for deck in get_device_manager().enumerate():
        deck.open()
        try:
            infos.append(
                {
                    "type": deck.deck_type(),
                    "serial": deck.get_serial_number(),
                    "key_count": deck.key_count(),
                }
            )
        finally:
            if deck.is_open():
                deck.close()
    return infos


def update_deck_statuses_safely(session):
    """Update device connection statuses in the database safely."""
    try:
        streamdecks = get_device_manager().enumerate()

        # De-duplicate decks sharing a serial number (e.g. the dummy transport
        # enumerates one device per known product ID) so DB inserts stay unique.
        seen_serials = set()
        deck_infos = []
        for deck in streamdecks:
            info = get_device_metadata(deck)
            if info.id in seen_serials:
                continue
            seen_serials.add(info.id)
            deck_infos.append(info)
        connected_ids = [info.id for info in deck_infos]

        devices_in_db = session.query(StreamDeckDevice).all()
        db_ids = {device.id for device in devices_in_db}

        # Add new connected devices not in DB
        for deck in deck_infos:
            if deck.id not in db_ids:
                session.add(deck)

        session.commit()
        return connected_ids
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Database error during device status update: {e}")
    except Exception as e:
        print(f"Unexpected error during device status update: {e}")
    return []


# -----------------------------
# Devices
# -----------------------------
@app.get("/devices", response_model=list[StreamDeckDevice], tags=["Devices"])
async def get_devices():
    with get_session() as session:
        online_device_ids = update_deck_statuses_safely(session)
        devices = session.query(StreamDeckDevice).all()
        for device in devices:
            device.connected = device.id in online_device_ids
        return devices


@app.put(
    "/device/{device_id}/config/{config_id}",
    response_model=StreamDeckDevice,
    status_code=200,
    tags=["Devices"],
)
def assign_config_to_device(device_id: str, config_id: str):
    with get_session() as session:
        device = session.get(StreamDeckDevice, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        config = session.get(StreamDeckConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        device.current_config_id = config_id
        session.commit()
        session.refresh(device)
        return device


# -----------------------------
# Runner dialect boundary
# -----------------------------
def to_runner_format(config_json: dict) -> dict:
    """Translate an API-dialect config dict (aliased camelCase, as served by
    every endpoint) into the RUNNER's internal format (snake_case). The API
    storage format must not dictate the CLI runner format: the runner core
    reads exactly one shape — device_type — and this boundary is the only
    place the wire dialect is translated. Unknown keys pass through so the
    runner's own parsers keep seeing everything the config carries."""
    if not isinstance(config_json, dict):
        return config_json
    out = dict(config_json)
    if "deviceType" in out:
        out["device_type"] = out.pop("deviceType")
    return out


@app.get("/device/{device_id}/config", tags=["Devices"])
def get_assigned_config(device_id: str):
    """The config currently assigned to a device (used by the device runner)."""
    with get_session() as session:
        device = session.get(StreamDeckDevice, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        # Serialize by alias so the device dialect matches every other
        # endpoint (camelCase: currentConfigId, activeAgentId). Readers
        # tolerate the snake_case spelling too, but the wire contract is
        # aliased per the API dialect.
        device_json = json.loads(device.model_dump_json(by_alias=True))
        if not device.current_config_id:
            return {"config": None, "device": device_json}
        config = session.get(StreamDeckConfig, device.current_config_id)
        if not config:
            return {"config": None, "device": device_json}
        return {
            "config": to_runner_format(
                json.loads(config.model_dump_json(by_alias=True))
            ),
            "device": device_json,
        }


# -----------------------------
# Configs
# -----------------------------
@app.get("/configs", response_model=list[StreamDeckConfig], tags=["Configs"])
async def list_configs():
    """
    Returns all configs. Each entry follows the OpenAPI StreamDeckConfig schema.
    """
    with get_session() as session:
        return session.query(StreamDeckConfig).all()


@app.get("/config/{config_id}", response_model=StreamDeckConfig, tags=["Configs"])
def get_config(config_id: str):
    with get_session() as session:
        config = session.get(StreamDeckConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        return config


@app.delete("/config/{config_id}", response_model=StreamDeckConfig, tags=["Configs"])
def delete_config(config_id: str):
    with get_session() as session:
        config = session.get(StreamDeckConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        # The dashboard reads current_config_id from device rows; leaving a
        # deleted config id there would surface a dead link in the UI.
        for device in session.query(StreamDeckDevice).all():
            if device.current_config_id == config_id:
                device.current_config_id = None
        session.delete(config)
        session.commit()
        return config


@app.post("/config", response_model=StreamDeckConfig, status_code=201, tags=["Configs"])
def create_config(config: StreamDeckConfig):
    with get_session() as session:
        session.add(config)
        session.commit()
        session.refresh(config)
        return config


@app.put(
    "/config/{config_id}", response_model=StreamDeckConfig, status_code=200, tags=["Configs"]
)
def update_config(config_id: str, config: StreamDeckConfig):
    with get_session() as session:
        saved_config = session.get(StreamDeckConfig, config_id)
        if not saved_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        saved_config.buttons = config.buttons
        saved_config.name = config.name
        saved_config.device_type = config.device_type
        # R5 (P16): triggers round-trip through the whole-row PUT — a body
        # without a triggers block clears it (replace semantics, matching
        # how buttons/name/deviceType behave).
        saved_config.triggers = config.triggers
        # P19: backgrounds follow the same replace semantics as triggers —
        # a payload without a backgrounds key clears the block.
        saved_config.backgrounds = config.backgrounds
        session.commit()
        session.refresh(saved_config)
        return saved_config


# -----------------------------
# Agents (nominated computers)
# -----------------------------
@app.get("/agents", response_model=list[Agent], tags=["Agents"])
def list_agents():
    """All registered agents (computers that can execute button actions)."""
    with get_session() as session:
        return session.query(Agent).all()


@app.post("/agents", response_model=Agent, status_code=201, tags=["Agents"])
def register_agent(agent: Agent):
    """Register (or idempotently re-register) an agent computer."""
    with get_session() as session:
        existing = session.get(Agent, agent.id)
        if existing:
            existing.hostname = agent.hostname
            existing.user = agent.user
            existing.platform = agent.platform
            existing.last_seen = agent.last_seen
            session.commit()
            session.refresh(existing)
            return existing
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return agent


@app.delete("/agents/{agent_id}", response_model=Agent, tags=["Agents"])
def delete_agent(agent_id: str):
    with get_session() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        # Clear any device nomination pointing at this agent.
        for device in session.query(StreamDeckDevice).all():
            if device.active_agent_id == agent_id:
                device.active_agent_id = None
        session.delete(agent)
        session.commit()
        return agent


@app.put("/device/{device_id}/agent/{agent_id}", response_model=StreamDeckDevice, tags=["Agents"])
def nominate_agent(device_id: str, agent_id: str):
    """Nominate the agent (computer) that a device's button actions target."""
    with get_session() as session:
        device = session.get(StreamDeckDevice, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        device.active_agent_id = agent_id
        session.commit()
        session.refresh(device)
        return device


@app.delete("/device/{device_id}/agent", response_model=StreamDeckDevice, tags=["Agents"])
def clear_agent_nomination(device_id: str):
    """Clear the nominated agent for a device (actions fall back to local)."""
    with get_session() as session:
        device = session.get(StreamDeckDevice, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        device.active_agent_id = None
        session.commit()
        session.refresh(device)
        return device


@app.get("/agents/{agent_id}/actions", tags=["Agents"])
def poll_actions(agent_id: str):
    """Agent long-poll: fetch pending actions (marks them as dispatched)."""
    with get_session() as session:
        if not session.get(Agent, agent_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        pending = (
            session.query(AgentAction)
            .filter(AgentAction.agent_id == agent_id)
            .filter(AgentAction.status == "pending")
            .order_by(AgentAction.created_at)
            .all()
        )
        # Serialize BEFORE committing status changes: commit expires ORM
        # attributes, and FastAPI's list serialization of aliased SQLModel
        # table models has field-mangling quirks.
        payload = [a.model_dump(mode="json", by_alias=True) for a in pending]
        for action in pending:
            action.status = "dispatched"
        session.commit()
        return JSONResponse(content=payload)


@app.post(
    "/agents/{agent_id}/actions/{action_id}/result",
    response_model=AgentAction,
    tags=["Agents"],
)
def report_action_result(action_id: str, result: dict):
    """Agent reports the outcome of an executed action."""
    with get_session() as session:
        action = session.get(AgentAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        action.status = result.get("status", "done")
        action.result = result
        session.commit()
        session.refresh(action)
        return action


@app.post("/agent-actions", response_model=AgentAction, status_code=202, tags=["Agents"])
def enqueue_action(action: AgentAction):
    """
    Queue an action for an agent (used by the device runner when a pressed
    button nominates a computer, and handy for testing via curl).
    """
    with get_session() as session:
        if not session.get(Agent, action.agent_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        action.status = "pending"
        session.add(action)
        session.commit()
        session.refresh(action)
        return action


@app.on_event("startup")
def on_startup() -> None:
    init_db()