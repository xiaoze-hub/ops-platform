from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    os: Mapped[str] = mapped_column(String(100), default="")
    agent_version: Mapped[str] = mapped_column(String(50), default="")
    token: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (Index("ix_metrics_node_id_timestamp", "node_id", "timestamp"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), index=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
