# models.py — StreamDeckConfig + StreamDeckDevice (SQLModel)
# Ported from streamdeck/api/models.py @ 078b8b23 (repo streamdeck, main).

from typing import Any, Optional
import uuid

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON, Text


class StreamDeckConfig(SQLModel, table=True):
    """
    SQLModel mapping for configs table.
    Buttons are stored as a JSON blob.
    """

    id: Optional[str] = Field(
        primary_key=True, index=True, default_factory=lambda: str(uuid.uuid4())
    )
    name: str
    device_type: str = Field(alias="deviceType")
    buttons: dict[str, Any] = Field(sa_column=Column("buttons", JSON), default=[])
    # R5 (P16): automatic-switching triggers, schema-less like buttons —
    # {"app": ["Slack"], "network": {"ssid": "...", "interface": "en0"}}.
    # No strict validation: the dialect stays flexible; the runner's
    # evaluator treats malformed shapes as no-match.
    triggers: dict[str, Any] | None = Field(
        default=None, sa_column=Column("triggers", JSON, nullable=True)
    )


class StreamDeckDevice(SQLModel, table=True):
    """
    SQLModel mapping for devices table.
    """

    id: Optional[str] = Field(default=None, primary_key=True, index=True)
    type: str
    name: str
    connected: bool = Field(default=False)
    current_config_id: str | None = Field(
        default=None, alias="currentConfigId"
    )
    active_agent_id: str | None = Field(
        default=None, alias="activeAgentId"
    )


class Agent(SQLModel, table=True):
    """
    A nominated computer running `streamdeck agent`, reachable to execute
    button actions on behalf of a Stream Deck.
    """

    id: str = Field(primary_key=True, index=True)  # agent-generated UUID
    hostname: str
    user: str | None = None
    platform: str | None = None
    active: bool = Field(default=True)
    last_seen: str | None = None


class AgentAction(SQLModel, table=True):
    """
    A queued action destined for an agent (nominate-a-computer flow).
    Lifecycle: pending -> dispatched -> done|failed.
    """

    id: Optional[str] = Field(
        primary_key=True, index=True, default_factory=lambda: str(uuid.uuid4())
    )
    agent_id: str = Field(index=True, alias="agentId")
    button_index: int | None = Field(default=None, alias="buttonIndex")
    device_id: str | None = Field(default=None, alias="deviceId")
    action: dict[str, Any] = Field(sa_column=Column("action", JSON))
    status: str = Field(default="pending", index=True)
    created_at: str | None = Field(default=None, alias="createdAt")
    result: dict[str, Any] | None = Field(
        default=None, sa_column=Column("result", JSON)
    )