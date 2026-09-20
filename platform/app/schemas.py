from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class NodeRegister(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    hostname: str = ""
    ip: str = ""
    os: str = ""
    agent_version: str = ""
    token: str


class MetricsIn(BaseModel):
    cpu_percent: float | None = None
    mem_percent: float | None = None
    disk_percent: float | None = None
    load_avg: float | None = None


class HeartbeatIn(BaseModel):
    metrics: MetricsIn | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)
    command_results: list[dict[str, Any]] = Field(default_factory=list)


class CommandResultIn(BaseModel):
    status: str = Field(pattern="^(done|failed)$")
    result: str = ""


class NodeOut(BaseModel):
    node_id: str
    hostname: str
    ip: str
    os: str
    agent_version: str
    status: str
    online: bool
    last_seen_at: datetime | None
    created_at: datetime | None = None
    cpu_percent: float | None = None
    mem_percent: float | None = None
    disk_percent: float | None = None
    load_avg: float | None = None

    model_config = {"from_attributes": True}


class NodeDetailOut(NodeOut):
    pass


class MetricOut(BaseModel):
    cpu_percent: float | None = None
    mem_percent: float | None = None
    disk_percent: float | None = None
    load_avg: float | None = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class LogOut(BaseModel):
    id: int
    node_id: str
    level: str
    content: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class CommandCreate(BaseModel):
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class CommandOut(BaseModel):
    id: int
    node_id: str
    action: str
    params: dict[str, Any]
    status: str
    result: str | None = None
    created_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class PendingCommand(BaseModel):
    id: int
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class HeartbeatOut(BaseModel):
    ok: bool = True
    pending_commands: list[PendingCommand] = Field(default_factory=list)
